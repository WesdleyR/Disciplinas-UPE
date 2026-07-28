# 📘 Disciplinas UPE

Aplicativo desktop feito em **Python + PySide6** para ajudar estudantes da **Universidade de Pernambuco (UPE)** a planejar a graduação: acompanhe disciplinas cursadas, pré-requisitos, co-requisitos e o progresso geral do curso, tudo em uma interface simples e com suporte a tema claro/escuro automático.

![status](https://img.shields.io/badge/status-em%20desenvolvimento-blue)
![license](https://img.shields.io/github/license/WesdleyR/Disciplinas-UPE)

## ✨ Funcionalidades

- ✅ Marcar disciplinas já cursadas (com salvamento automático em JSON)
- 📊 Barra de progresso por bloco de disciplinas (Básico, Profissional, Eletivas)
- 🔓 Identificação automática de disciplinas **disponíveis**, **bloqueadas** e **cursadas**, com base em pré-requisitos e co-requisitos
- 🔍 Pesquisa por nome, código, período, pré-requisito ou co-requisito
- 🌗 Detecção automática de tema claro/escuro do sistema
- 🗂️ Organização por abas (grade básica, profissional e eletivas)

## 🖥️ Como usar

### Rodando a partir do código-fonte
\`\`\`bash
git clone https://github.com/WesdleyR/Disciplinas-UPE.git
cd Disciplinas-UPE
pip install -r requirements.txt
python main.py
\`\`\`

## 🛠️ Tecnologias

- Python 3
- PySide6 (Qt for Python)
- darkdetect (detecção de tema do sistema)
- PyInstaller (empacotamento do executável)

## 📄 Estrutura do projeto

\`\`\`
sheets/          → módulos com as disciplinas de cada bloco (básico, profissional, eletivas)
main.py          → aplicação principal (interface e lógica)
completed_courses.json → progresso salvo localmente
\`\`\`

## 🤝 Contribuindo

Sugestões, correções de disciplinas/pré-requisitos ou melhorias de interface são bem-vindas! Abra uma issue ou envie um pull request.

## 📜 Licença

Este projeto está sob a licença MIT.
