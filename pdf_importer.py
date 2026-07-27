"""
pdf_importer.py

Lógica de leitura do PDF do "Perfil Curricular" impresso do SIGA-UPE
(com os blocos de Pré-Requisitos/Co-Requisitos abaixo de cada disciplina).
Usado tanto pelo app principal (botão "Importar PDF do SIGA") quanto pelo
script de linha de comando gerar_disciplinas.py.

Requisitos:
    pip install pdfplumber
"""

import re
import pdfplumber

# Marcadores de seção usados pelo próprio relatório do SIGA para indicar
# a qual ciclo cada disciplina pertence. Isso é mais confiável do que
# tentar adivinhar pelo período.
SECTION_MARKERS = [
    (re.compile(r'CICLO\s+GERAL\s+OU\s+CICLO\s+B[ÁA]SICO', re.IGNORECASE), 'basico'),
    (re.compile(r'CICLO\s+PROFISSIONAL\s+OU\s+TRONCO\s+COMUM', re.IGNORECASE), 'profissional'),
    (re.compile(r'COMPONENTES\s+ELETIVOS', re.IGNORECASE), 'eletivas'),
]

# A partir daqui o documento só tem informações de resumo, não mais disciplinas.
STOP_MARKER = re.compile(r'Resumo\s+Carga\s+Hor[áa]ria\s+do\s+Perfil', re.IGNORECASE)

# Código de disciplina: letras (com acentos raros) + números, ex: MATM0001, ELET0013
CODE_RE = r'[A-ZÇÁÉÍÓÚÂÊÎÔÛÃÕ]{3,6}\d{3,6}'
HEADER_RE = re.compile(rf'(?:^|\n)\s*({CODE_RE})\s*-\s*', re.MULTILINE)
DATA_RE = re.compile(
    rf'(OBRIGAT[ÓO]RIO|ELETIVO)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.,]+)'
)
PREREQ_RE = re.compile(r'Pr[ée]-Requisitos:\s*(.*?)\s*Co-Requisitos:', re.DOTALL | re.IGNORECASE)
COREQ_RE = re.compile(
    r'Co-Requisitos:\s*(.*?)\s*(?:Requisito Carga Hor[áa]ria:|Equival[êe]ncias:|Ementa:)',
    re.DOTALL | re.IGNORECASE,
)
CODE_FINDALL_RE = re.compile(CODE_RE)

# Cabeçalho da tabela que o SIGA repete no topo de cada página impressa.
# Quando uma disciplina cai bem numa quebra de página, esse texto aparece
# encaixado entre pedaços do nome (ou entre o nome e a linha de dados) e
# precisa ser removido antes de tentar extrair qualquer coisa.
PAGE_HEADER_NOISE_RE = re.compile(
    r'CH\s+CH\s+CH\s+CH\s*\n?\s*'
    r'Componente\s+Curricular\s+Tipo\s+Per[íi]odo\s+Cr[ée]ditos\s*\n?\s*'
    r'Te[óo]rica\s+Pr[áa]tica\s+Extensionista\s+Total\s*\n?',
    re.IGNORECASE,
)


class PDFImportError(Exception):
    """Erro amigável para exibir numa caixa de diálogo do app."""
    pass


def extract_text(pdf_path):
    """Extrai o texto de todas as páginas do PDF, uma após a outra."""
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            full_text.append(page_text)
    combined = "\n".join(full_text)
    return PAGE_HEADER_NOISE_RE.sub(' ', combined)


def parse_requisitos(raw):
    """Converte o texto de Pré-Requisitos/Co-Requisitos em lista de códigos.
    'Não existem ...' vira lista vazia. 'Fórmula: A E B' vira ['A', 'B']."""
    if raw is None:
        return []
    if 'não exist' in raw.lower():
        return []
    return CODE_FINDALL_RE.findall(raw)


def clean_name(raw_name):
    """Remove quebras de linha e espaços duplicados de um nome de disciplina."""
    return re.sub(r'\s+', ' ', raw_name).strip().upper()


def parse_courses(full_text):
    """Percorre o texto completo identificando os blocos de cada disciplina
    e a seção (básico/profissional/eletivas) em que cada uma foi encontrada.
    Retorna (courses, warnings)."""

    stop_match = STOP_MARKER.search(full_text)
    if stop_match:
        full_text = full_text[:stop_match.start()]

    section_positions = []
    for pattern, category in SECTION_MARKERS:
        for m in pattern.finditer(full_text):
            section_positions.append((m.start(), category))
    section_positions.sort()

    def section_at(pos):
        current = None
        for start, category in section_positions:
            if start <= pos:
                current = category
            else:
                break
        return current

    headers = list(HEADER_RE.finditer(full_text))
    courses = []
    warnings = []

    for i, header_match in enumerate(headers):
        code = header_match.group(1)
        block_start = header_match.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(full_text)
        block = full_text[block_start:block_end]

        data_match = DATA_RE.search(block)
        if not data_match:
            warnings.append(f'{code}: não encontrei a linha de tipo/período/CH/créditos, disciplina ignorada.')
            continue

        tipo = data_match.group(1).upper()
        period = int(data_match.group(2))
        ch_total = int(data_match.group(6))
        credits = float(data_match.group(7).replace(',', '.'))

        name_part_before = block[:data_match.start()]
        prereq_marker = re.search(r'Pr[ée]-Requisitos:', block, re.IGNORECASE)
        name_part_after_end = prereq_marker.start() if prereq_marker else len(block)
        name_part_after = block[data_match.end():name_part_after_end]
        name = clean_name(name_part_before + ' ' + name_part_after)

        prereq_match = PREREQ_RE.search(block)
        coreq_match = COREQ_RE.search(block)
        prerequisites = parse_requisitos(prereq_match.group(1) if prereq_match else None)
        corequisites = parse_requisitos(coreq_match.group(1) if coreq_match else None)

        section = section_at(header_match.start())
        if section is None:
            if 'ELETIV' in tipo:
                section = 'eletivas'
            elif period <= 4:
                section = 'basico'
            else:
                section = 'profissional'
            warnings.append(f'{code}: nenhuma seção do SIGA encontrada antes dela, classificada por período/tipo.')

        courses.append({
            'category': section,
            'code': code,
            'name': name,
            'period': period,
            'hours': ch_total,
            'credits': credits,
            'prerequisites': prerequisites,
            'corequisites': corequisites,
        })

    return courses, warnings


def format_list(codes):
    return '[' + ', '.join(f'"{c}"' for c in codes) + ']'


def build_file_content(courses):
    sorted_courses = sorted(courses, key=lambda c: c['name'])
    lines = []
    for c in sorted_courses:
        lines.append(
            f'    {{"code": "{c["code"]}", "name": "{c["name"]}", "period": {c["period"]}, '
            f'"prerequisites": {format_list(c["prerequisites"])}, '
            f'"corequisites": {format_list(c["corequisites"])}, '
            f'"hours": {c["hours"]}, "credits": {c["credits"]:.1f}}},'
        )
    if lines:
        lines[-1] = lines[-1].rstrip(',')
    return 'DISCIPLINAS = [\n' + '\n'.join(lines) + '\n] \n'


def import_pdf(pdf_path):
    """Lê o PDF e retorna um dicionário {'basico': [...], 'profissional': [...],
    'eletivas': [...]} de disciplinas, além da lista de avisos de parsing.
    Levanta PDFImportError se nada for reconhecido."""
    full_text = extract_text(pdf_path)
    courses, warnings = parse_courses(full_text)

    if not courses:
        raise PDFImportError(
            "Não reconheci nenhuma disciplina nesse PDF. Confirme que é o "
            "relatório de Perfil Curricular do SIGA, gerado com os blocos de "
            "Pré-Requisitos/Co-Requisitos habilitados."
        )

    by_category = {'basico': [], 'profissional': [], 'eletivas': []}
    for c in courses:
        by_category[c['category']].append(c)

    return by_category, warnings
