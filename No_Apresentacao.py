import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class ApresentacaoNode(Node):
    def __init__(self):
        super().__init__('apresentacao_node')

        # Publicador apontando para o tópico que o No_fala.py escuta
        self.pub_fala = self.create_publisher(String, '/resposta_bot', 10)

        self.timer = self.create_timer(3.0, self._fazer_apresentacao)
        self.ja_falou = False

        self.get_logger().info('Nó de Apresentação iniciado. Aguardando para saudar o operador...')

    def _fazer_apresentacao(self):
        if not self.ja_falou:
            texto_apresentacao = "Olá, serei seu assistente neste período de aprendizagem. Estou na escuta, câmbio."

            # Monta o JSON com a estrutura exata que o No_fala.py precisa para rodar
            payload = {
                'respostas': [texto_apresentacao],
                'confianca': 1.0,
                'streaming': False
            }

            msg = String()
            msg.data = json.dumps(payload, ensure_ascii=False)

            self.pub_fala.publish(msg)
            self.get_logger().info(f'Apresentacação enviada: "{texto_apresentacao}"')

            self.ja_falou = True
            self.timer.cancel() # para o timer para não ter duas apresentações


    def main(args=None):
        rclpy.init(args=args)
        node = ApresentacaoNode()
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()

    if __name__ == '__main__':
        main()