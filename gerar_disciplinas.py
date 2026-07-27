#!/usr/bin/env python3
"""
gerar_disciplinas.py

Versão de linha de comando: lê o PDF do "Perfil Curricular" impresso do
SIGA-UPE e gera basico.py, profissional.py e eletivas.py numa pasta de saída.

A lógica de leitura/parsing fica em pdf_importer.py (o mesmo módulo usado
pelo botão "Importar PDF do SIGA" dentro do app). Use este script se preferir
gerar os arquivos fora do app, ou para automatizar em outro contexto.

Uso:
    python gerar_disciplinas.py caminho/para/SIGUPE.pdf [pasta_saida]

Requisitos:
    pip install pdfplumber
"""

import sys
import os
from pdf_importer import import_pdf, build_file_content, PDFImportError


def main():
    if len(sys.argv) < 2:
        print('Uso: python gerar_disciplinas.py caminho/para/SIGUPE.pdf [pasta_saida]')
        sys.exit(1)

    pdf_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else '.'
    os.makedirs(out_dir, exist_ok=True)

    print(f'Lendo {pdf_path}...')
    try:
        by_category, warnings = import_pdf(pdf_path)
    except PDFImportError as e:
        print(f'Erro: {e}')
        sys.exit(1)

    total = 0
    for category, filename in [
        ('basico', 'basico.py'),
        ('profissional', 'profissional.py'),
        ('eletivas', 'eletivas.py'),
    ]:
        content = build_file_content(by_category[category])
        out_path = os.path.join(out_dir, filename)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  {filename}: {len(by_category[category])} disciplina(s) -> {out_path}')
        total += len(by_category[category])

    if warnings:
        print(f'\n{len(warnings)} aviso(s):')
        for w in warnings:
            print(f'  - {w}')

    print(f'\nTotal: {total} disciplina(s) reconhecida(s).')


if __name__ == '__main__':
    main()
