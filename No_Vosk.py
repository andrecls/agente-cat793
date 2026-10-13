import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import vosk
import sounddevice as sd
import queue
import sys

class ReconhecedorDeVoz(Node):
    def __init__(self):
        super().__init__('no_vosk')
        # Publicador normal para o Rasa
        self.publisher_ = self.create_publisher(String, '/texto_operador', 10)
        
        # NOVO: Publicador de atalho para o LLM (simulando o Rasa)
        self.pub_atalho_llm = self.create_publisher(String, '/resposta_rasa', 10)
        
        caminho_modelo = "model" 
        try:
            self.model = vosk.Model(caminho_modelo)
        except Exception as e:
            self.get_logger().error(f"Erro: Modelo não encontrado.")
            sys.exit(1)
            
        self.q = queue.Queue()
        self.get_logger().info("Microfone ativado. Aguardando fala...")

    def audio_callback(self, indata, frames, time, status):
        self.q.put(bytes(indata))

    def escutar(self):
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                               channels=1, callback=self.audio_callback):
            
            rec = vosk.KaldiRecognizer(self.model, 16000)
            
            while rclpy.ok():
                data = self.q.get()
                if rec.AcceptWaveform(data):
                    resultado = json.loads(rec.Result())
                    texto = resultado.get("text", "")
                    
                    if texto:
                        self.get_logger().info(f"🎤 Você disse: '{texto}'")
                        
                        # --- GATILHO DE TESTE ---
                        if "teste" in texto.lower():
                            payload = {
                                'texto_original': texto,
                                'intencao': 'teste_de_sistema',
                                'entidades': [],
                                'evento': {}
                            }
                            msg_teste = String()
                            msg_teste.data = json.dumps(payload, ensure_ascii=False)
                            self.pub_atalho_llm.publish(msg_teste)
                            self.get_logger().info("Gatilho de teste acionado. JSON enviado ao LLM.")
                        else:
                            # Fluxo normal: envia texto puro para o Rasa
                            msg = String()
                            msg.data = texto
                            self.publisher_.publish(msg)
                            
                rclpy.spin_once(self, timeout_sec=0)

def main(args=None):
    rclpy.init(args=args)
    node = ReconhecedorDeVoz()
    try:
        node.escutar()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()