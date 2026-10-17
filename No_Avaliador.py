import rclpy
from rclpy.node import Node
from sirv_msgs.msg import SirvVehicleTelemetry, CAT793FVehicleControl, CAT793FPanelControl
from std_msgs.msg import String
import json

class AvaliadorEmTempoReal(Node):
    def __init__(self):
        super().__init__('avaliador_cenarios')
        
        # 1. Antena de Telemetria Física
        self.sub_telemetria = self.create_subscription(
            SirvVehicleTelemetry, '/cat793f/telemetry', self.telemetria_callback, 10)
            
        # 2. Antena de Controles do Veículo (Pedais)
        self.sub_controles = self.create_subscription(
            CAT793FVehicleControl, '/cat793f/vehicle_control', self.controles_callback, 10)
            
        # 3. Antena do Painel (Cinto e Botões)
        self.sub_painel = self.create_subscription(
            CAT793FPanelControl, '/cat793f/panel_control', self.painel_callback, 10)
            
        # 4. Antena de Voz do Operador
        self.sub_voz = self.create_subscription(
            String, '/texto_operador', self.voz_callback, 10)
            
        # Publicador para o LLM
        self.llm_publisher = self.create_publisher(String, '/resposta_rasa', 10)
        
        # Memória do estado atual do caminhão
        self.estado = {
            'velocidade': 0.0,
            'rpm': 0.0,
            'marcha': 0,
            'bascula': 0.0,
            'freio_servico': 0.0,
            'freio_retardador': 0.0,
            'cinto_seguranca': False
        }
        
        # Timer para enviar o "Raio-X" ao LLM a cada 3 segundos
        self.timer_avaliacao = self.create_timer(3.0, self.avaliar_estado)
        self.get_logger().info("Máquina de Estados iniciada. Monitorizando telemetria, pedais e voz...")

    def telemetria_callback(self, msg):
        self.estado['velocidade'] = msg.speed
        self.estado['rpm'] = msg.enginerpm
        self.estado['marcha'] = msg.gear
        self.estado['bascula'] = msg.tryposition

    def controles_callback(self, msg):
        self.estado['freio_servico'] = msg.brake
        self.estado['freio_retardador'] = msg.brakeretarder

    def painel_callback(self, msg):
        self.estado['cinto_seguranca'] = msg.seatbelt

    def avaliar_estado(self):
        infracao = None
        
        v = self.estado['velocidade']
        cinto = self.estado['cinto_seguranca']
        bascula = self.estado['bascula']
        freio_servico = self.estado['freio_servico']
        marcha = self.estado['marcha']

        # O PYTHON ESCREVE A MENSAGEM FINAL DE RÁDIO:
        if v > 0.0 and not cinto:
            infracao = "Atenção operador, o caminhão está em movimento sem o cinto de segurança. Pare o equipamento imediatamente e coloque o cinto. Câmbio."
            
        elif v > 0.0 and bascula > 0.0:
            infracao = "Atenção operador, o caminhão está se movendo com a báscula levantada. Pare imediatamente e apoie a báscula. Câmbio."
            
        elif v > 5.0 and freio_servico > 0.0:
            infracao = "Operador, velocidade incompatível para o freio de serviço. Utilize o freio retardador. Câmbio."
            
        elif v > 0.0 and marcha == 0:
            infracao = "Atenção operador, proibido locomover em neutro. Engate a marcha correta. Câmbio."

        if infracao:
            # Ordem de "Papagaio" (Bypass dos filtros de segurança)
            prompt_ia = (
                f"Sua ÚNICA tarefa é repetir o texto a seguir exatamente como ele está escrito. "
                f"Não adicione nenhuma palavra, não recuse o pedido e não dê explicações. "
                f"TEXTO: {infracao}"
            )
            self._enviar_para_llm(prompt_ia)

    def voz_callback(self, msg):
        fala = msg.data.strip().lower()
        if fala:
            # Avaliação condicional para emergências relatadas por voz
            if "fogo" in fala or "incêndio" in fala or "emergência" in fala:
                diretriz = "Emergência detectada. Ordene imediatamente a parada do caminhão, aplicação do freio de estacionamento e desligamento do motor."
            else:
                diretriz = "Responda à dúvida do operador de forma curta e profissional."
                
            prompt_voz = (
                f"[FALA DO OPERADOR]: '{fala}'. "
                f"[DIRETRIZ PARA O RÁDIO]: {diretriz} "
                f"Formule a resposta no rádio encerrando com 'câmbio'."
            )
            self._enviar_para_llm(prompt_voz)

    def _enviar_para_llm(self, texto):
        payload = {'texto_original': texto}
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.llm_publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = AvaliadorEmTempoReal()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()