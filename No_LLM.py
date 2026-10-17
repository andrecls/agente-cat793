#!/usr/bin/env python3
# '/resposta_rasa' (JSON NLU) → Ollama → publica UMA ÚNICA resposta em '/resposta_bot'
import json
import threading
import ollama
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

MODELO_LLM    = 'llama3.2:1b'
MAX_HISTORICO = 1

SYSTEM_PROMPT = system_prompt = """Você é a Central de Comando (CCO) de segurança de um simulador CAT793F.
Sua ÚNICA função é ler a [DIRETRIZ PARA O RÁDIO] enviada pelo sistema e transformá-la em uma fala natural de rádio.

DIRETRIZES DE PERSONA:
- Fale em português brasileiro, agindo como um supervisor de mina firme e profissional.
- Use jargões de rádio (ex: "Positivo", "Na escuta", "Câmbio").
- NUNCA use aspas, formatações especiais, ou prefixos como "[RESPOSTA]".
- Cumpra exatamente o que a diretriz mandar. Se a diretriz mandar dar uma bronca sobre o cinto, fale apenas sobre o cinto.
"""

GUIA_DE_ACOES = {
    'solicitar_basculamento'        : 'Autorize o deslocamento. Lembre o operador de verificar o alinhamento e respeitar a sinalização na praça.',
    'solicitar_carregamento'        : 'Autorize o deslocamento para a frente de lavra. Peça atenção à fila de carregamento.',
    'solicitar_abastecimento'       : 'Autorize o deslocamento para o posto/comboio. Recomende atenção ao limite de velocidade.',
    'saudacao_radio'                : 'Responda brevemente que a CCO está em QAP (na escuta) e pronta para apoiar.',
    'solicitar_apoio_pista'         : 'Confirme que o equipamento de apoio já está a caminho.',
    'solicitar_ultrapassagem'       : 'Oriente o operador a fazer contato de rádio com o veículo à frente e aguardar permissão antes de ultrapassar.',
    'informar_veiculo_leve_proximo' : 'Alerta: Oriente o operador a não se aproximar a menos de 10 metros do veículo leve.',
    'informar_parada_abrupta_frente': 'Oriente o operador a manter distância segura, selecionar neutro e aplicar o freio de estacionamento.',
    'informar_falha_mecanica_eletrica': 'Ordene a parada total, aplicação do freio de estacionamento e desligamento do motor. Confirme que a manutenção será enviada.',
    'informar_falha_freio_direcao'  : 'Falha Critica: Ordene a parada imediata, freio de estacionamento e desligamento do motor. Confirme envio de resgate urgente.',
    'informar_superaquecimento'     : 'Oriente a parar, selecionar Neutro e aumentar o RPM acima de 1200 por mais de 5 segundos para resfriamento.',
    'informar_emergencia_incendio'  : 'Comando Critico: Ordene parada total, freio de estacionamento, corte do motor e acionamento do sistema de supressão de incêndio.',
    'informar_baixa_visibilidade_poeira': 'Oriente a parar, engatar neutro e aplicar freio de estacionamento devido à poeira perigosa.',
    'informar_emergencia_area_radio': 'Protocolo de Emergência: Ordene veículo parado, freio de estacionamento, neutro e silêncio no rádio até liberação.',
    'informar_problema_mecanico'    : 'Ordene a parada total, aplicação do freio de estacionamento e desligamento do motor. Confirme que a manutenção será enviada.',
    'informar_falha_critica'        : 'Falha Critica: Ordene a parada imediata, freio de estacionamento e desligamento do motor. Confirme envio de resgate urgente.',
    'informar_emergencia'           : 'Protocolo de Emergência: Ordene veículo parado, freio de estacionamento, neutro e silêncio no rádio até liberação.',
    'informar_condicao_via'         : 'Oriente o operador a reduzir velocidade e manter distância segura. Registre a condição da via.',
    'informar_status_operacional'   : 'Confirme o status recebido e oriente o operador sobre o próximo passo.',
    'confirmar_entendimento'        : 'Confirme brevemente que a CCO recebeu e está monitorando.',
    'confirmar_entendimento'        : 'Confirme brevemente que a CCO recebeu e está monitorando.',
    'teste_de_sistema'              : 'Responda exatamente com a frase: Sistema funcionando, palavras foram interpretadas com sucesso, câmbio.'
}



class LLMNode(Node):
    def __init__(self):
        super().__init__('llm_node')
        self._historico   = []
        self._lock        = threading.Lock()
        self._processando = False

        self.pub = self.create_publisher(String, '/resposta_bot', 10)
        self.create_subscription(String, '/resposta_rasa', self._cb, 10)
        self.get_logger().info(f'No Ollama iniciado ({MODELO_LLM}). Aguardando em /resposta_rasa...')

    def _cb(self, msg: String):
        with self._lock:
            if self._processando:
                self.get_logger().warn('Mensagem ignorada: LLM ja esta gerando uma resposta.')
                return
            self._processando = True

        try:
            dados          = json.loads(msg.data)
            texto_original = dados.get('texto_original', '')
            intencao       = dados.get('intencao', '')
            entidades      = dados.get('entidades', [])
            evento         = dados.get('evento', {})

            threading.Thread(
                target=self._gerar_resposta,
                args=(texto_original, intencao, entidades, evento),
                daemon=True,
            ).start()

        except json.JSONDecodeError as e:
            self.get_logger().error(f'JSON invalido: {e}')
            with self._lock:
                self._processando = False

    def _gerar_resposta(self, texto_original: str, intencao: str, entidades: list, evento: dict):
        try:
            ents_str     = ', '.join(f"{e.get('valor')}" for e in entidades) if entidades else 'nenhum detalhe especifico'
            instrucao    = GUIA_DE_ACOES.get(intencao, 'Responda ao que o motorista disse de forma breve.')
            contexto_evento = self._montar_contexto_evento(evento)

            prompt_llm = (
                f"{contexto_evento}"
                f"O motorista informou: '{texto_original}' (Detalhes: {ents_str})\n"
                f"Sua tarefa: {instrucao}\n"
                "Escreva agora a sua resposta para o radio:"
            )

            with self._lock:
                self._historico.append({'role': 'user', 'content': prompt_llm})
                if len(self._historico) > MAX_HISTORICO * 2:
                    self._historico[:] = self._historico[-(MAX_HISTORICO * 2):]
                historico_snapshot = list(self._historico)

            resposta = ollama.chat(
                model=MODELO_LLM,
                messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, *historico_snapshot],
                stream=False,
                keep_alive=-1,
                options={
                    'num_gpu'    : 0,
                    'temperature': 0.1,
                    'num_predict': 80,
                    'num_ctx'    : 512,
                    'stop'       : ['\n', 'Motorista:', 'CCO:', 'Sua tarefa:']
                }
            )

            texto_completo = resposta.get('message', {}).get('content', '').replace('"', '').strip()

            if texto_completo:
                self.get_logger().info(f'[LLM] Resposta: "{texto_completo}"')
                with self._lock:
                    self._historico.append({'role': 'assistant', 'content': texto_completo})
                self._publicar_resposta(texto_completo)
            else:
                self.get_logger().warn('[LLM] Resposta vazia.')

        except Exception as e:
            self.get_logger().error(f'Erro ao consultar o LLM: {e}')
        finally:
            with self._lock:
                self._processando = False

    def _montar_contexto_evento(self, evento: dict) -> str:
        if not evento:
            return ''
        return (
            f"Contexto do evento ativo na simulacao:\n"
            f"- Evento: {evento.get('Nome', '')}\n"
            f"- Situacao: {evento.get('Estimulo', '')}\n"
            f"- Criterios esperados: {evento.get('Criterios', '')}\n\n"
        )

    def _publicar_resposta(self, texto: str):
        payload  = {'respostas': [texto], 'streaming': False}
        out      = String()
        out.data = json.dumps(payload, ensure_ascii=False)
        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = LLMNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
