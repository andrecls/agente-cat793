#!/usr/bin/env python3
import json, queue, threading, rclpy, traceback, os, subprocess
from rclpy.node import Node
from std_msgs.msg import String

# Caminhos exatos dos arquivos do Piper TTS que configuramos
PIPER_BIN = '/home/andre/cco_ia/piper_voices/piper/piper'
PIPER_MODEL = '/home/andre/cco_ia/piper_voices/pt_BR-faber-medium.onnx'
ARQUIVO_AUDIO = '/home/andre/cco_ia/piper_voices/saida.wav'

CONFIANCA_MINIMA = 0.70
_ENCERRAR = object()

class FalaNode(Node):
    def __init__(self):
        super().__init__('fala_node')
        self.ultima_fala = ''
        self._fila_fala  = queue.Queue()
        self._parar      = threading.Event()
        
        self.get_logger().info('Iniciando motor de voz Piper TTS (Offline)...')
        self.get_logger().info('Voz do Faber ativada! Pronto para falar.')
        
        threading.Thread(target=self._loop_audio, daemon=True, name='piper-audio').start()
        self.create_subscription(String, '/resposta_bot', self._cb, 10)

    def _cb(self, msg: String):
        try:
            dados     = json.loads(msg.data)
            texto     = ' '.join(dados.get('respostas', []))
            texto     = texto.replace('"','').replace("'",'').replace('*','').replace('\n',' ').strip()
            confianca = dados.get('confianca', 1.0)
            streaming = dados.get('streaming', False)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'JSON inválido: {e}')
            return

        if not texto or confianca < CONFIANCA_MINIMA: return
        if not streaming and texto == self.ultima_fala: return
        if not streaming: self.ultima_fala = texto

        self.get_logger().info(f'Enfileirando: "{texto}"')
        self._fila_fala.put(texto)

    def _loop_audio(self):
        while not self._parar.is_set():
            try:
                texto = self._fila_fala.get(block=True, timeout=0.1)
            except queue.Empty:
                continue
            if texto is _ENCERRAR: break
            self._sintetizar_e_tocar(texto)
            self._fila_fala.task_done()

    def _sintetizar_e_tocar(self, texto: str):
        try:
            # 1. Gera o áudio com o binário do Piper
            comando_tts = f'echo "{texto}" | {PIPER_BIN} -m {PIPER_MODEL} -f {ARQUIVO_AUDIO}'
            subprocess.run(comando_tts, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 2. Toca o arquivo WAV gerado usando o tocador nativo do Ubuntu
            self.get_logger().info(f'Reproduzindo: {texto}')
            os.system(f'aplay {ARQUIVO_AUDIO} -q')

        except Exception:
            self.get_logger().error(f'Erro ao processar/tocar:\n{traceback.format_exc()}')

    def destroy_node(self):
        self._parar.set()
        self._fila_fala.put(_ENCERRAR)
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    n = FalaNode()
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass
    finally:
        n.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()