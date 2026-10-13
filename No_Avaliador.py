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

    def voz_callback(self, msg):
        fala = msg.data.strip()
        if fala:
            frase_contexto = (
                f"[FALA DO OPERADOR]: O operador disse: '{fala}'. "
                f"Contexto atual: Vel {self.estado['velocidade']:.1f} km/h, "
                f"RPM {self.estado['rpm']:.0f}, Marcha {self.estado['marcha']}, "
                f"Báscula {self.estado['bascula']:.1f}%. "
            )
            self._enviar_para_llm(frase_contexto)

    def avaliar_estado(self):
        cinto_status = "COLOCADO" if self.estado['cinto_seguranca'] else "SOLTO"
        
        raiox = (
            
            f"[TELEMETRIA]: Vel: {self.estado['velocidade']:.1f} km/h | "
            f"Cinto: {cinto_status} | RPM: {self.estado['rpm']:.0f} | "
            f"Báscula: {self.estado['bascula']:.1f}%."
        )
        
        self._enviar_para_llm(raiox)

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