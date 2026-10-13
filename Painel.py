import tkinter as tk
from tkinter import scrolledtext
import subprocess
import signal
import threading
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import os

# --- PALETA DE CORES (DARK THEME) ---
BG_PRINCIPAL = "#1E1E1E"
BG_PAINEL = "#2D2D2D"
FG_TEXTO = "#E0E0E0"
COR_VERDE_FLAT = "#27AE60"
COR_VERMELHO_FLAT = "#C0392B"
COR_AZUL_DESTAQUE = "#2980B9"

class NóMonitor(Node):
    """Nó ROS 2 invisível que escuta os tópicos e também fala"""
    def __init__(self, callback_tela):
        super().__init__('painel_monitor')
        self.callback_tela = callback_tela
        
        # Inscrições para ouvir a rede
        self.create_subscription(String, '/texto_operador', self.cb_operador, 10)
        self.create_subscription(String, '/resposta_rasa', self.cb_json, 10)
        self.create_subscription(String, '/resposta_bot', self.cb_bot, 10)
        
        # NOVO: Publicador para enviar falas diretamente para o módulo de voz
        self.pub_fala = self.create_publisher(String, '/resposta_bot', 10)

    def cb_operador(self, msg):
        self.callback_tela(f"🎤 [VOZ CAPTURADA]: {msg.data}\n", "azul")

    def cb_json(self, msg):
        try:
            dados = json.loads(msg.data)
            json_bonito = json.dumps(dados, indent=2, ensure_ascii=False)
            self.callback_tela(f"⚙ [AVALIADOR/LOGIC]:\n{json_bonito}\n", "laranja")
        except:
            self.callback_tela(f"⚙️️ [SISTEMA]: {msg.data}\n", "laranja")

    def cb_bot(self, msg):
        try:
            dados = json.loads(msg.data)
            texto_fala = dados.get("respostas", [""])[0]
            self.callback_tela(f"🤖 [TUTOR IA]: {texto_fala}\n", "verde")
        except:
            # Se for apenas um texto direto (como a nossa mensagem de boas vindas)
            self.callback_tela(f"🤖 [TUTOR IA]: {msg.data}\n", "verde")
            
    def falar_direto(self, texto):
        """Envia a frase formatada em JSON para o Piper não dar erro"""
        msg = String()
        
        # Cria o "pacote" exatamente igual ao que o LLM gera
        pacote_falso_llm = {
            "respostas": [texto]
        }
        
        # Converte para JSON e publica no tópico
        msg.data = json.dumps(pacote_falso_llm, ensure_ascii=False)
        self.pub_fala.publish(msg)


class PainelTutorIA:
    def __init__(self, root):
        self.root = root
        self.root.title("Tutor Inteligente - CAT793F")
        self.root.geometry("850x650")
        self.root.configure(bg=BG_PRINCIPAL)
        
        self.processos_ativos = []
        self.node = None # Será preenchido depois

        # --- CABEÇALHO ---
        frame_header = tk.Frame(root, bg=COR_AZUL_DESTAQUE, height=50)
        frame_header.pack(fill=tk.X)
        
        titulo = tk.Label(frame_header, text="CCO - SISTEMA DE TUTORIA INTELIGENTE (CAT793F)", 
                          bg=COR_AZUL_DESTAQUE, fg="#FFFFFF", font=("Segoe UI", 14, "bold"))
        titulo.pack(pady=10)

        # --- ÁREA DE CONTROLES ---
        frame_controles = tk.Frame(root, bg=BG_PAINEL, bd=0, relief="flat")
        frame_controles.pack(pady=15, padx=20, fill=tk.X)

        self.btn_iniciar = tk.Button(frame_controles, text="▶ LIGAR MÓDULOS DE IA", 
                                     font=("Segoe UI", 11, "bold"), bg=COR_VERDE_FLAT, fg="white", 
                                     relief="flat", activebackground="#2ECC71", activeforeground="white",
                                     cursor="hand2", command=self.iniciar_tudo)
        self.btn_iniciar.pack(side=tk.LEFT, padx=10, pady=15, expand=True, fill=tk.X)

        self.btn_parar = tk.Button(frame_controles, text="⬛ PARAR SISTEMA", 
                                   font=("Segoe UI", 11, "bold"), bg=COR_VERMELHO_FLAT, fg="white", 
                                   relief="flat", activebackground="#E74C3C", activeforeground="white",
                                   cursor="hand2", state=tk.DISABLED, command=self.parar_tudo)
        self.btn_parar.pack(side=tk.RIGHT, padx=10, pady=15, expand=True, fill=tk.X)

        # --- STATUS DA CONEXÃO ---
        frame_status = tk.Frame(root, bg=BG_PRINCIPAL)
        frame_status.pack(fill=tk.X, padx=20)
        
        self.lbl_indicador = tk.Label(frame_status, text="⬤", fg="gray", bg=BG_PRINCIPAL, font=("Segoe UI", 14))
        self.lbl_indicador.pack(side=tk.LEFT)
        
        self.lbl_status = tk.Label(frame_status, text="SISTEMA OFFLINE - Aguardando inicialização...", 
                                   fg="gray", bg=BG_PRINCIPAL, font=("Segoe UI", 10, "bold"))
        self.lbl_status.pack(side=tk.LEFT, padx=5)

        # --- TERMINAL DE LOGS ---
        frame_terminal = tk.Frame(root, bg=BG_PRINCIPAL)
        frame_terminal.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)
        
        self.console = scrolledtext.ScrolledText(frame_terminal, wrap=tk.WORD, bg="#0C0C0C", fg=FG_TEXTO, 
                                                 font=("Consolas", 11), relief="flat", padx=10, pady=10)
        self.console.pack(fill=tk.BOTH, expand=True)
        
        self.console.tag_config("azul", foreground="#00E5FF")
        self.console.tag_config("laranja", foreground="#FFB300")
        self.console.tag_config("verde", foreground="#00E676")
        self.console.tag_config("vermelho", foreground="#FF1744")
        self.console.tag_config("branco", foreground="#FFFFFF")
        
        self.inserir_log("Sistema Pronto. Clique em 'Ligar Módulos de IA' para estabelecer conexão.\n", "branco")

    def inserir_log(self, texto, cor="branco"):
        self.console.insert(tk.END, texto, cor)
        self.console.see(tk.END)

    def iniciar_tudo(self):
        self.lbl_indicador.config(fg=COR_VERDE_FLAT)
        self.lbl_status.config(text="SISTEMA ONLINE - Módulos ativos e escutando a rede", fg=COR_VERDE_FLAT)
        self.inserir_log("\n[SISTEMA] Inicializando orquestração de módulos...\n", "laranja")
        
        try:
            ambiente_ros = os.environ.copy()
            
            p_avaliador = subprocess.Popen(["python3", "No_Avaliador.py"], env=ambiente_ros)
            p_llm = subprocess.Popen(["python3", "No_LLM.py"], env=ambiente_ros)
            p_vosk = subprocess.Popen(["python3", "No_Vosk.py"], env=ambiente_ros)
            p_fala = subprocess.Popen(["python3", "No_Fala.py"], env=ambiente_ros)
            
            self.processos_ativos.extend([p_avaliador, p_llm, p_vosk, p_fala])
            
            self.btn_iniciar.config(state=tk.DISABLED, bg="#7f8c8d")
            self.btn_parar.config(state=tk.NORMAL, bg=COR_VERMELHO_FLAT)
            self.inserir_log("[SISTEMA] Módulos de IA iniciados!\n", "verde")
            self.inserir_log("--------------------------------------------------\n", "branco")
            
            # NOVO: Agenda a mensagem de boas-vindas para daqui a 4 segundos (4000 ms)
            # Dá tempo suficiente para o subprocesso do Piper TTS carregar a voz
            self.root.after(4000, self.dar_boas_vindas)
            
        except Exception as e:
            self.inserir_log(f"[ERRO CRÍTICO]: {e}\n", "vermelho")

    def dar_boas_vindas(self):
        """Envia a frase inicial para o sistema de áudio e tela"""
        frase = "Olá, operador! Eu serei o seu instrutor de inteligência artificial durante este processo de aprendizado."
        if self.node:
            self.node.falar_direto(frase)

    def parar_tudo(self):
        self.lbl_indicador.config(fg="gray")
        self.lbl_status.config(text="SISTEMA OFFLINE - Aguardando inicialização...", fg="gray")
        self.inserir_log("\n[SISTEMA] Encerrando processos e libertando portas...\n", "vermelho")
        
        for p in self.processos_ativos:
            p.send_signal(signal.SIGINT)
        self.processos_ativos.clear()
        
        self.btn_iniciar.config(state=tk.NORMAL, bg=COR_VERDE_FLAT)
        self.btn_parar.config(state=tk.DISABLED, bg="#7f8c8d")

    def fechar_aplicativo(self):
        self.parar_tudo()
        self.root.destroy()


def iniciar_interface():
    rclpy.init()
    janela = tk.Tk()
    app = PainelTutorIA(janela)
    
    node = NóMonitor(app.inserir_log)
    app.node = node # Conecta o nó ROS 2 ao aplicativo Visual
    
    thread_ros = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    thread_ros.start()
    
    janela.protocol("WM_DELETE_WINDOW", app.fechar_aplicativo)
    janela.mainloop()
    
    rclpy.shutdown()

if __name__ == "__main__":
    iniciar_interface()