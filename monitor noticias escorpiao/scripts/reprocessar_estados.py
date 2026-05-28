#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reprocessa as notícias com estado 'Não identificado' no noticias.json,
aplicando as 3 camadas de detecção (texto RSS → sigla contexto → HTML do artigo).
"""

import json
import time
import sys
import os

# Importa a classe do script principal
sys.path.insert(0, os.path.dirname(__file__))
from buscar_noticias import BuscadorNoticias


def reprocessar():
    buscador = BuscadorNoticias()

    caminho = os.path.join(os.path.dirname(__file__), '..', 'noticias.json')
    caminho = os.path.normpath(caminho)

    print("=" * 65)
    print("🔁 REPROCESSAMENTO DE ESTADOS NÃO IDENTIFICADOS")
    print("=" * 65)

    # Carrega base existente
    with open(caminho, 'r', encoding='utf-8') as f:
        noticias = json.load(f)

    nao_identificados = [
        n for n in noticias
        if not n.get('estado') or n['estado'] == 'Não identificado'
    ]

    total = len(nao_identificados)
    print(f"\n📋 Total na base: {len(noticias)}")
    print(f"❓ Não identificados: {total}\n")

    if total == 0:
        print("✅ Nenhum registro para reprocessar.")
        return

    corrigidos = 0
    ainda_sem_estado = 0

    for i, noticia in enumerate(nao_identificados, 1):
        titulo   = noticia.get('titulo', '')
        descricao = noticia.get('descricao', '')
        link     = noticia.get('link', '')

        print(f"[{i}/{total}] {titulo[:70]}")

        cidade, estado = buscador.resolver_localizacao(titulo, descricao, link)

        if estado and estado != 'Não identificado':
            noticia['estado'] = estado
            if cidade and cidade != 'Não identificada':
                noticia['cidade'] = cidade
            print(f"  ✅ {estado} — {cidade}")
            corrigidos += 1
        else:
            print(f"  ⚠️  Ainda não identificado")
            ainda_sem_estado += 1

        # Respeita rate limit entre fetches de artigo
        time.sleep(0.3)

    # Salva resultado
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 65)
    print(f"✅ Corrigidos:            {corrigidos}")
    print(f"⚠️  Ainda sem estado:     {ainda_sem_estado}")
    print(f"📰 Total na base:         {len(noticias)}")
    print("=" * 65)
    print(f"\n💾 noticias.json atualizado em: {caminho}")


if __name__ == '__main__':
    reprocessar()
