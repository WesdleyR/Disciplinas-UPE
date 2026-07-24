import sys
import os
import json
import importlib.util
import darkdetect
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QCheckBox, QLabel, QLineEdit, QHBoxLayout, QProgressBar)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon

def resource_path(relative_path):
    """Obtém o caminho absoluto para o recurso, funcionando tanto em desenvolvimento quanto compilado"""
    try:
        # PyInstaller cria uma pasta temp e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    return os.path.join(base_path, relative_path)

def app_dir_path(relative_path):
    """Obtém um caminho gravável ao lado do executável (ou do script, em
    desenvolvimento). Usado para arquivos que precisam persistir entre
    execuções, como o progresso do usuário."""
    if getattr(sys, "frozen", False):
        # Rodando como executável compilado (PyInstaller)
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disciplinas UPE - Por WesdleyR")
        self.setMinimumSize(1200, 800)
        
        # Configurar o ícone da janela
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        
        # Definir o caminho do arquivo de dados
        # IMPORTANTE: não usar resource_path() aqui. Em modo --onefile, o
        # PyInstaller extrai os recursos para uma pasta temporária (_MEIPASS)
        # que é apagada ao fechar o app — gravar o progresso ali faria os
        # dados sumirem no próximo uso. Por isso salvamos ao lado do
        # executável (ou do script, em modo desenvolvimento), que é um
        # local estável e gravável.
        self.data_file = self.get_data_file_path()
        
        # Inicializar tema atual
        self.is_dark = darkdetect.isDark()
        self.colors = self.get_theme_colors()
        
        # Configurar timer para verificar mudanças de tema
        self.theme_timer = QTimer()
        self.theme_timer.timeout.connect(self.check_theme)
        self.theme_timer.start(1000)  # Verifica a cada 1 segundo
        
        # Definir estilo global
        self.apply_stylesheet()

        # Inicializar dicionário de todas as disciplinas
        self.all_courses = {}

        # Nomes dos módulos (arquivos em sheets/) considerados obrigatórios
        # para fins do progresso geral do curso. "eletivas" fica de fora
        # porque o aluno não precisa cursar todas elas, só uma quantidade
        # mínima de créditos — incluir todas distorceria o percentual.
        self.mandatory_modules = {"basico", "profissional"}
        self.mandatory_codes = []
        
        # Inicializar conjunto de disciplinas completadas
        self.completed_courses = self.load_completed_courses()

        # Widget central: barra de progresso geral do curso + abas
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(20, 15, 20, 10)
        central_layout.setSpacing(8)

        overall_label = QLabel("Progresso total do curso (disciplinas obrigatórias):")
        overall_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 13px; font-weight: bold;")
        central_layout.addWidget(overall_label)
        self.overall_label = overall_label

        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setTextVisible(True)
        self.overall_progress_bar.setFixedHeight(22)
        self.overall_progress_bar.setStyleSheet(self.get_progress_bar_stylesheet())
        central_layout.addWidget(self.overall_progress_bar)

        self.tabs = QTabWidget()
        central_layout.addWidget(self.tabs)

        self.setCentralWidget(central_widget)

        # Carregar módulos da pasta sheets
        self.load_sheet_modules()

        # Calcula o progresso geral assim que os módulos são carregados
        self.update_overall_progress()

    def get_data_file_path(self):
        """Retorna o caminho gravável para o arquivo de progresso do usuário."""
        return app_dir_path("completed_courses.json")

    def load_sheet_modules(self):
        # A pasta "sheets" é um recurso somente-leitura embutido no
        # executável (veja --add-data no requirements.txt / .spec), então
        # usamos resource_path (que aponta para _MEIPASS quando compilado).
        sheets_dir = resource_path("sheets")
        
        if not os.path.exists(sheets_dir):
            print(f"Diretório {sheets_dir} não encontrado")
            return

        # Carrega cada módulo apenas uma vez (antes era carregado 2x: uma
        # para montar all_courses e outra para criar as abas)
        loaded_modules = []
        for filename in sorted(os.listdir(sheets_dir)):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]

                spec = importlib.util.spec_from_file_location(
                    module_name,
                    os.path.join(sheets_dir, filename)
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "DISCIPLINAS"):
                    loaded_modules.append((module_name, module))
                    # Adicionar disciplinas ao dicionário global
                    for disciplina in module.DISCIPLINAS:
                        self.all_courses[disciplina["code"]] = disciplina
                        if module_name.lower() in self.mandatory_modules:
                            self.mandatory_codes.append(disciplina["code"])

        # Depois, crie as abas reaproveitando os módulos já carregados
        for module_name, module in loaded_modules:
            tab = QWidget()
            self.tabs.addTab(tab, module_name.capitalize())
            self.setup_tab(tab, module.DISCIPLINAS)

    def setup_tab(self, tab, disciplinas):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Adicionar instrução
        instruction = QLabel("Clique nas caixas de seleção para marcar as disciplinas que você já cursou.\n"
                           "As disciplinas disponíveis para cursar serão destacadas em verde.")
        instruction.setStyleSheet(f"""
            QLabel {{
                background-color: {self.colors['tab_inactive']};
                padding: 15px;
                border-radius: 8px;
                font-size: 14px;
                color: {self.colors['accent']};
                border: 1px solid {self.colors['border']};
            }}
        """)
        layout.addWidget(instruction)

        # Adicionar campo de pesquisa
        search_layout = QHBoxLayout()
        search_label = QLabel("Pesquisar:")
        search_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 14px;")
        search_input = QLineEdit()
        search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors['input_background']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 8px;
                color: {self.colors['text']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors['accent']};
            }}
        """)
        search_input.setPlaceholderText("Digite para filtrar disciplinas...")
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_input)
        layout.addLayout(search_layout)

        # Adicionar barra de progresso de conclusão do curso
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setTextVisible(True)
        progress_bar.setFixedHeight(22)
        progress_bar.setStyleSheet(self.get_progress_bar_stylesheet())
        layout.addWidget(progress_bar)

        # Criar tabela
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            "Período", "Cursada?", "Código", "Disciplina", "Status",
            "Pré-requisitos", "Co-requisitos"
        ])

        # Configurar fonte
        font = QFont("Segoe UI", 10)
        table.setFont(font)

        # Configurar dados da tabela
        sorted_data = sorted(disciplinas, key=lambda x: (x["period"], x["name"]))
        table.setRowCount(len(sorted_data))

        # Preencher a tabela (código existente)
        self.populate_table(table, sorted_data)

        # Conectar o campo de pesquisa à função de filtro
        search_input.textChanged.connect(lambda text: self.filter_table(table, text, sorted_data))

        # Ajustar tamanho das colunas (código existente)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(table)
        tab.setLayout(layout)

        # Guarda a lista completa (não filtrada) de códigos desta aba,
        # usada para calcular o progresso mesmo quando a tabela estiver filtrada
        tab.all_codes = [item["code"] for item in sorted_data]

        self.update_table(table)
        self.update_progress(tab)

    def populate_table(self, table, data):
        """Preenche a tabela com os dados fornecidos"""
        for row, item in enumerate(data):
            # Período
            period_item = QTableWidgetItem(f"{item['period']}º")
            period_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            period_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Torna a célula somente leitura
            table.setItem(row, 0, period_item)

            # Checkbox para "Cursada?"
            checkbox = QCheckBox()
            checkbox.setChecked(item["code"] in self.completed_courses)
            checkbox.stateChanged.connect(lambda state, code=item["code"]: self.toggle_course(code))
            cell_widget = QWidget()
            cell_layout = QVBoxLayout(cell_widget)
            cell_layout.addWidget(checkbox)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            table.setCellWidget(row, 1, cell_widget)

            # Código
            code_item = QTableWidgetItem(item["code"])
            code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            code_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Torna a célula somente leitura
            table.setItem(row, 2, code_item)

            # Nome da disciplina
            name_item = QTableWidgetItem(item["name"])
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Torna a célula somente leitura
            table.setItem(row, 3, name_item)

            # Status
            status_item = QTableWidgetItem("Bloqueada")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Torna a célula somente leitura
            table.setItem(row, 4, status_item)

            # Pré-requisitos
            prereqs = ", ".join(item["prerequisites"]) if item["prerequisites"] else "Nenhum"
            prereqs_item = QTableWidgetItem(prereqs)
            prereqs_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Torna a célula somente leitura
            table.setItem(row, 5, prereqs_item)

            # Co-requisitos
            coreqs = ", ".join(item["corequisites"]) if item["corequisites"] else "Nenhum"
            coreqs_item = QTableWidgetItem(coreqs)
            coreqs_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Torna a célula somente leitura
            table.setItem(row, 6, coreqs_item)

    def filter_table(self, table, search_text, original_data):
        """Filtra a tabela com base no texto de pesquisa"""
        search_text = search_text.lower()
        
        # Se a pesquisa estiver vazia, restaura todos os dados
        if not search_text:
            table.setRowCount(len(original_data))
            self.populate_table(table, original_data)
            self.update_table(table)
            return

        # Filtra os dados
        filtered_data = [
            item for item in original_data
            if search_text in item["name"].lower() or
               search_text in item["code"].lower() or
               str(item["period"]) == search_text or
               any(search_text in prereq.lower() for prereq in item["prerequisites"]) or
               any(search_text in coreq.lower() for coreq in item["corequisites"])
        ]

        # Atualiza a tabela com os dados filtrados
        table.setRowCount(len(filtered_data))
        self.populate_table(table, filtered_data)
        self.update_table(table)

    def is_available(self, course, _visited=None):
        # _visited evita recursão infinita quando duas (ou mais) disciplinas
        # são co-requisito umas das outras (ciclo A -> B -> A, ou cadeias
        # maiores A -> B -> C -> A).
        if _visited is None:
            _visited = set()
        if course["code"] in _visited:
            # Já estamos verificando esta disciplina nesta mesma cadeia de
            # chamadas: isso significa que caímos de volta nela através de
            # um ciclo de co-requisitos. Retornamos True (e não False) para
            # quebrar a recursão sem bloquear o grupo indevidamente — os
            # pré-requisitos "de verdade" desta disciplina já foram (ou
            # serão) conferidos na chamada original dela, mais acima na
            # pilha; aqui estamos só confirmando que o ciclo é consistente,
            # não pulando nenhuma verificação real. Com o "return False"
            # antigo, duas disciplinas mutuamente co-requisito nunca
            # ficavam "Disponível" mesmo quando podiam ser cursadas juntas.
            return True
        _visited.add(course["code"])

        # Verifica se todos os pré-requisitos foram completados
        prereqs_met = all(prereq in self.completed_courses for prereq in course["prerequisites"])
        
        # Verifica se todos os co-requisitos foram completados ou estão disponíveis
        coreqs_met = all(
            coreq in self.completed_courses or 
            (coreq in self.all_courses and self.is_available(self.all_courses[coreq], _visited))
            for coreq in course["corequisites"]
        )

        return prereqs_met and coreqs_met

    def load_completed_courses(self):
        """Carrega as disciplinas cursadas do arquivo JSON"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    return set(json.load(f))
        except Exception as e:
            print(f"Erro ao carregar disciplinas cursadas: {e}")
        return set()

    def save_completed_courses(self):
        """Salva as disciplinas cursadas em um arquivo JSON"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(list(self.completed_courses), f)
        except Exception as e:
            print(f"Erro ao salvar disciplinas cursadas: {e}")

    def toggle_course(self, code):
        """Atualiza o estado de conclusão da disciplina"""
        if code in self.completed_courses:
            self.completed_courses.remove(code)
        else:
            self.completed_courses.add(code)
        
        # Salvar alterações no arquivo
        self.save_completed_courses()
        
        # Atualizar todas as tabelas
        self.update_all_tables()

    def update_all_tables(self):
        # Atualizar todas as abas
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            table = tab.findChild(QTableWidget)
            if table:
                self.update_table(table)
            self.update_progress(tab)

        # Atualizar também a barra de progresso geral do curso
        self.update_overall_progress()

    def get_progress_bar_stylesheet(self):
        """Retorna o CSS da barra de progresso, de acordo com o tema atual"""
        return f"""
            QProgressBar {{
                border: 1px solid {self.colors['border']};
                border-radius: 6px;
                background-color: {self.colors['tab_inactive']};
                text-align: center;
                color: {self.colors['text']};
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {self.colors['accent']};
                border-radius: 5px;
            }}
        """

    def update_progress(self, tab):
        """Atualiza a barra de progresso de uma aba com base nas disciplinas concluídas"""
        progress_bar = tab.findChild(QProgressBar)
        all_codes = getattr(tab, "all_codes", None)
        if not progress_bar or not all_codes:
            return

        total = len(all_codes)
        completed = sum(1 for code in all_codes if code in self.completed_courses)
        percent = int(round((completed / total) * 100)) if total else 0

        progress_bar.setValue(percent)
        progress_bar.setFormat(f"{completed}/{total} disciplinas concluídas ({percent}%)")

    def update_overall_progress(self):
        """Atualiza a barra de progresso geral do curso, considerando
        apenas as disciplinas obrigatórias (básico + profissional)."""
        if not hasattr(self, "overall_progress_bar"):
            return

        total = len(self.mandatory_codes)
        completed = sum(1 for code in self.mandatory_codes if code in self.completed_courses)
        percent = int(round((completed / total) * 100)) if total else 0

        self.overall_progress_bar.setValue(percent)
        self.overall_progress_bar.setFormat(f"{completed}/{total} disciplinas obrigatórias concluídas ({percent}%)")

    def update_table(self, table):
        for row in range(table.rowCount()):
            code = table.item(row, 2).text()
            completed = code in self.completed_courses
            
            course_data = self.all_courses.get(code)

            if course_data:
                available = not completed and self.is_available(course_data)

                status_item = table.item(row, 4)
                if completed:
                    status_text = "Cursada"
                    row_color = QColor(self.colors['completed'])
                elif available:
                    status_text = "Disponível"
                    row_color = QColor(self.colors['available'])
                else:
                    status_text = "Bloqueada"
                    row_color = QColor(self.colors['blocked'])
                    
                status_item.setText(status_text)
                
                # Aplicar cor de fundo à linha
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item:
                        item.setBackground(row_color)

    def closeEvent(self, event):
        """Sobrescreve o evento de fechamento para garantir que os dados sejam salvos"""
        self.save_completed_courses()
        super().closeEvent(event)

    def get_theme_colors(self):
        """Retorna as cores baseadas no tema do sistema"""
        if self.is_dark:
            return {
                'background': '#1e1e1e',
                'tab_background': '#2d2d2d',
                'tab_inactive': '#252525',
                'border': '#333',
                'text': '#ddd',
                'text_selected': '#fff',
                'grid': '#3d3d3d',
                'header': '#252525',
                'input_background': '#252525',
                'accent': '#58a6ff',
                'completed': '#1a365d',  # Azul escuro
                'available': '#1b4332',  # Verde escuro
                'blocked': '#2d2d2d',    # Cinza escuro
            }
        else:
            return {
                'background': '#f0f0f0',
                'tab_background': '#ffffff',
                'tab_inactive': '#e8e8e8',
                'border': '#d0d0d0',
                'text': '#000000',
                'text_selected': '#000000',
                'grid': '#e0e0e0',
                'header': '#f5f5f5',
                'input_background': '#ffffff',
                'accent': '#0066cc',
                'completed': '#cce5ff',  # Azul claro
                'available': '#d4edda',  # Verde claro
                'blocked': '#ffffff',    # Branco
            }

    def check_theme(self):
        """Verifica se houve mudança no tema do sistema"""
        current_theme = darkdetect.isDark()
        if current_theme != self.is_dark:
            self.is_dark = current_theme
            self.colors = self.get_theme_colors()
            self.update_theme()

    def apply_stylesheet(self):
        """Monta e aplica a folha de estilo global com base em self.colors.
        Centralizado aqui para ser reaproveitado tanto na inicialização
        quanto na troca de tema (update_theme), evitando manter dois
        blocos de CSS idênticos sincronizados manualmente."""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {self.colors['background']};
            }}
            QTabWidget::pane {{
                border: 1px solid {self.colors['border']};
                border-radius: 5px;
                background: {self.colors['tab_background']};
            }}
            QTabBar::tab {{
                background: {self.colors['tab_inactive']};
                border: 1px solid {self.colors['border']};
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: {self.colors['text']};
            }}
            QTabBar::tab:selected {{
                background: {self.colors['tab_background']};
                border-bottom-color: {self.colors['tab_background']};
                color: {self.colors['text_selected']};
            }}
            QTableWidget {{
                border: 1px solid {self.colors['border']};
                border-radius: 5px;
                background-color: {self.colors['tab_background']};
                gridline-color: {self.colors['grid']};
                color: {self.colors['text']};
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QHeaderView::section {{
                background-color: {self.colors['header']};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {self.colors['border']};
                color: {self.colors['text']};
                font-weight: bold;
            }}
            QCheckBox {{
                margin: 5px;
                color: {self.colors['text']};
            }}
            QLineEdit {{
                background-color: {self.colors['input_background']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 8px;
                color: {self.colors['text']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors['accent']};
            }}
            QLabel {{
                color: {self.colors['text']};
            }}
        """)

    def update_theme(self):
        """Atualiza o tema da aplicação"""
        # Atualizar estilo global
        self.apply_stylesheet()

        # Atualizar a barra de progresso geral do curso
        if hasattr(self, "overall_label"):
            self.overall_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 13px; font-weight: bold;")
        if hasattr(self, "overall_progress_bar"):
            self.overall_progress_bar.setStyleSheet(self.get_progress_bar_stylesheet())

        # Atualizar todas as abas
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            
            # Atualizar instrução
            instruction = tab.findChild(QLabel)
            if instruction:
                instruction.setStyleSheet(f"""
                    QLabel {{
                        background-color: {self.colors['tab_inactive']};
                        padding: 15px;
                        border-radius: 8px;
                        font-size: 14px;
                        color: {self.colors['accent']};
                        border: 1px solid {self.colors['border']};
                    }}
                """)
            
            # Atualizar campo de pesquisa
            search_label = tab.findChildren(QLabel)[1] if len(tab.findChildren(QLabel)) > 1 else None
            if search_label:
                search_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 14px;")
            
            search_input = tab.findChild(QLineEdit)
            if search_input:
                search_input.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {self.colors['input_background']};
                        border: 1px solid {self.colors['border']};
                        border-radius: 4px;
                        padding: 8px;
                        color: {self.colors['text']};
                        font-size: 14px;
                    }}
                    QLineEdit:focus {{
                        border: 1px solid {self.colors['accent']};
                    }}
                """)

            # Atualizar barra de progresso
            progress_bar = tab.findChild(QProgressBar)
            if progress_bar:
                progress_bar.setStyleSheet(self.get_progress_bar_stylesheet())
            self.update_progress(tab)

            # Atualizar tabela
            table = tab.findChild(QTableWidget)
            if table:
                self.update_table(table)

if __name__ == "__main__":
    app = QApplication([])
    app.setWindowIcon(QIcon(resource_path("icon.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())