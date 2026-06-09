#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import os
import re
import time
import sys
import warnings
import xml.etree.ElementTree as ET
import unicodedata
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

# Compatibilidade Windows: força UTF-8 no terminal
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Suprime aviso de SSL (verify=False usado apenas para IBGE local)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')


class BuscadorNoticias:

    def __init__(self):
        self.noticias = []

        self.termos = [
            "escorpião Brasil",
            "escorpiões Brasil",
            "picada escorpião",
            "picada de escorpião",
            "acidente escorpiônico",
            "escorpionismo",
            "infestação escorpiões",
            "infestação de escorpiões",
            "escorpião amarelo",
            "soro antiescorpiônico",
            "animais peçonhentos escorpião",
            "prefeitura escorpião",
            "vigilância escorpião",
            "vigilância sanitária escorpião",
            "alerta escorpiões",
            "controle de escorpiões",
            "captura de escorpiões",
            "prevenção escorpiões",
            "criança escorpião",
            "morte escorpião",
            "escorpião prefeitura municipal",
            "escorpiões prefeitura municipal",
            "escorpião vigilância ambiental",
            "escorpiões vigilância ambiental"
        ]

        self.estados = {
            "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
            "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
            "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
            "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
            "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba",
            "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
            "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
            "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
            "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
            "TO": "Tocantins"
        }

        # Siglas que podem gerar falso positivo — tratadas com cuidado
        self.siglas_ambiguas = {"PA", "PI", "PE", "GO", "MS", "MT", "AL", "SE"}

        self.cidade_estado = self.carregar_cidades_ibge()

        # Palavras de 3 letras comuns em português que conflitam com nomes de cidades curtas
        self.palavras_comuns_3 = {
            "bom", "boa", "rio", "sao", "pao", "mar", "mau", "vez", "fim",
            "luz", "dia", "mes", "ano", "lei", "bem", "por", "ser", "ter",
            "ele", "ela", "nos", "dos", "das", "foi", "tem", "era", "ali",
            "ato", "cor", "tom", "som", "ver", "dar", "ler", "vir", "sai",
            "vai", "faz", "asa", "ceu", "uso", "sal", "mel", "rua", "paz",
            "dor", "lar", "sol", "sul", "pra", "pro", "eco", "ovo", "uva"
        }

        self.correcoes_manuais = {
            # Regiões administrativas do Distrito Federal (únicas no Brasil)
            "ceilandia": "DF",
            "taguatinga": "DF",
            "samambaia": "DF",
            "aguas claras": "DF",
            "nucleo bandeirante": "DF",
            "candangolandia": "DF",
            "paranoa": "DF",
            "lago sul": "DF",
            "lago norte": "DF",
            "riacho fundo": "DF",
            "vicente pires": "DF",
            "sol nascente": "DF",
            "estrutural": "DF",
            "itapoa": "DF",
            "jardim botanico": "DF",
            "park way": "DF",
            "sao sebastiao": "DF",
            # Correções SP
            "jaguariuna": "SP",
            "mococa": "SP",
            "votuporanga": "SP",
            "birigui": "SP",
            "conchal": "SP",
            "cacapava": "SP",
            "sao carlos": "SP",
            "votorantim": "SP",
            "tijucas": "SC",
            "gravatal": "SC",
            "xanxere": "SC",
            "itajai": "SC",
            "biguacu": "SC",
            "braco do norte": "SC",
            "mafra": "SC",
            "esteio": "RS",
            "sapucaia do sul": "RS",
            "sao leopoldo": "RS",
            "presidente kennedy": "ES",
            "laranja da terra": "ES",
            "rio largo": "AL",
            "buzios": "RJ",
            "ibipora": "PR"
        }

        self.cidade_estado.update(self.correcoes_manuais)

    # ─── Utilitários de texto ─────────────────────────────────────────────────

    def sem_acento(self, texto):
        texto = unicodedata.normalize("NFD", texto)
        texto = texto.encode("ascii", "ignore").decode("utf-8")
        return texto.lower().strip()

    def normalizar(self, texto):
        texto = self.sem_acento(texto)
        texto = re.sub(r"\s+", " ", texto)
        return texto.strip()

    # ─── Cidades IBGE ─────────────────────────────────────────────────────────

    def carregar_cidades_ibge(self):
        cidades = {}
        try:
            url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
            response = requests.get(url, timeout=20, verify=False)
            response.raise_for_status()
            dados = response.json()
            for item in dados:
                nome = item.get("nome", "")
                uf = item.get("microrregiao", {}).get("mesorregiao", {}).get("UF", {}).get("sigla", "")
                if nome and uf:
                    chave = self.normalizar(nome)
                    cidades[chave] = uf
            print(f"✅ {len(cidades)} municípios carregados do IBGE")
        except Exception as e:
            print(f"⚠️ Não foi possível carregar municípios do IBGE: {e}")
        return cidades

    def carregar_existentes(self):
        if os.path.exists("noticias.json"):
            try:
                with open("noticias.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    # ─── Limpeza e IDs ───────────────────────────────────────────────────────

    def limpar_html(self, texto):
        if not texto:
            return ""
        texto = re.sub(r"<.*?>", "", texto)
        texto = texto.replace("&nbsp;", " ").replace("&amp;", "&")
        texto = texto.replace("&#39;", "'").replace("&quot;", '"')
        return texto.strip()

    def normalizar_titulo(self, titulo):
        titulo = self.normalizar(titulo)
        titulo = re.sub(r" - .*?$", "", titulo)
        titulo = re.sub(r" \| .*?$", "", titulo)
        return titulo.strip()

    def gerar_id(self, titulo, link):
        base = self.normalizar_titulo(titulo)
        base = re.sub(r"[^a-z0-9]", "", base)
        return base[:150]

    def converter_data(self, pub_date):
        try:
            dt = parsedate_to_datetime(pub_date)
            if dt.year < 2026:
                return None
            return dt.strftime("%d/%m/%Y")
        except:
            return None

    # ─── Validação de notícia ─────────────────────────────────────────────────

    def noticia_valida(self, titulo, descricao):
        texto = self.normalizar(f"{titulo} {descricao}")

        bloqueios = [
            "horoscopo", "signo", "zodiaco", "astrologia",
            "taro", "previsao do dia", "escorpiao do signo",
            "signo de escorpiao", "cinema", "filme", "serie",
            "streaming", "netflix", "marvel", "dc comics",
            "personagem", "trailer", "bilheteria", "ator", "atriz",
            "musica", "show", "celebridade", "famosos", "bbb",
            "plantas para espantar", "planta para espantar",
            "espantar escorpiao", "espantar escorpioes",
            "repelente natural", "remedio caseiro", "dicas caseiras",
            "simpatia", "feng shui", "jardinagem", "plantas repelentes",
            "lavanda", "hortela", "alecrim", "plantas", "tv", "televisao"
        ]

        if any(b in texto for b in bloqueios):
            return False

        tem_escorpiao = any(t in texto for t in [
            "escorpiao", "escorpioes", "escorpionismo",
            "escorpionico", "escorpionica"
        ])

        if not tem_escorpiao:
            return False

        contexto_valido = [
            "picada", "acidente", "morte", "morreu", "obito",
            "soro", "antiescorpionico", "hospital", "atendimento",
            "crianca", "bebe", "infestacao", "aparecimento",
            "aumento", "prefeitura", "vigilancia", "saude",
            "alerta", "prevencao", "controle", "captura",
            "mutirao", "orienta", "orientacao",
            "animais peconhentos", "animal peconhento", "peconhentos",
            "residencia", "residencias", "casa", "casas",
            "morador", "moradores", "condominio", "condominios",
            "terreno", "lote", "bairro", "bairros",
            "verao", "chuvas", "calor", "limpeza", "entulho", "lixo",
            "dedetizacao", "dedetizadora", "controle de pragas",
            "risco", "perigo", "registro", "registra",
            "casos", "ocorrencias", "escorpiao amarelo", "escorpioes amarelos"
        ]

        return any(c in texto for c in contexto_valido)

    # ─── Gravidade ────────────────────────────────────────────────────────────

    def detectar_gravidade(self, texto):
        t = self.normalizar(texto)
        if any(p in t for p in ["morte", "morre", "morreu", "obito", "uti", "estado grave", "fatal"]):
            return "grave"
        if any(p in t for p in ["picada", "acidente", "soro", "hospital", "atendimento", "infestacao"]):
            return "moderada"
        return "leve"

    # ─── Detecção de localização — 3 camadas ─────────────────────────────────

    def cidade_permitida(self, nome_normalizado):
        """Retorna True se a cidade pode ser buscada (evita falsos positivos)."""
        n = len(nome_normalizado)
        if n < 3:
            return False
        if n == 3 and nome_normalizado in self.palavras_comuns_3:
            return False
        return True

    def detectar_localizacao(self, texto):
        """Busca cidade E estado em uma única passagem. Cidade confirma estado.

        Retorna (cidade_formatada, sigla_estado) ou (None, None).
        Cidades de 3+ chars são permitidas, exceto palavras comuns do português.
        """
        t = f" {self.normalizar(texto)} "
        cidades_ordenadas = sorted(self.cidade_estado.keys(), key=len, reverse=True)

        for cidade in cidades_ordenadas:
            if not self.cidade_permitida(cidade):
                continue
            if re.search(r"\b" + re.escape(cidade) + r"\b", t):
                estado = self.cidade_estado[cidade]
                return self.formatar_cidade(cidade), estado

        return None, None

    def detectar_estado_por_nome(self, texto):
        """Fallback: busca estado pelo nome completo ou por cidades do Pará."""
        t = f" {self.normalizar(texto)} "

        estados_extenso = {
            "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM",
            "bahia": "BA", "ceara": "CE", "distrito federal": "DF",
            "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
            "mato grosso do sul": "MS", "mato grosso": "MT",
            "minas gerais": "MG", "paraiba": "PB", "parana": "PR",
            "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
            "rio grande do norte": "RN", "rio grande do sul": "RS",
            "rondonia": "RO", "roraima": "RR", "santa catarina": "SC",
            "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO"
        }
        for nome, uf in estados_extenso.items():
            if nome in t:
                return uf

        # DF: contextos exclusivos do Distrito Federal
        if any(c in t for c in ["brasilia", "distrito federal", "plano piloto",
                                  "asa norte", "asa sul", "lago sul", "lago norte",
                                  "aguas claras", "taguatinga", "ceilandia"]):
            return "DF"

        # Pará: tratamento especial (evita confusão com preposição "para")
        if any(c in t for c in ["estado do para", "governo do para", "belem",
                                  "santarem", "maraba", "altamira", "castanhal",
                                  "ananindeua", "parauapebas", "cameta"]):
            return "PA"

        return None

    def detectar_sigla_contexto(self, texto):
        """Camada 2: detecta sigla de UF em padrões comuns de notícias.

        Reconhece formatos como: 'Cidade, SP', '(RJ)', '- MG', '/SP', 'em SP'.
        Evita siglas ambíguas sem contexto claro de delimitação.
        """
        siglas = "|".join(self.estados.keys())

        # Padrões confiáveis: sigla cercada por pontuação ou parênteses
        padroes_fortes = [
            rf'[,\-/]\s*({siglas})\b',       # ", SP"  "- MG"  "/RJ"
            rf'\(({siglas})\)',                # "(SP)"
            rf'\b({siglas})\s*[\-/,\)]',      # "SP,"  "SP-"  "SP/"
        ]
        for padrao in padroes_fortes:
            match = re.search(padrao, texto.upper())
            if match:
                sigla = match.group(1)
                # Siglas ambíguas exigem padrão forte (já estamos em padrão forte aqui)
                return sigla

        # Padrão solto: "em SP", "no RJ", "pelo DF" — só siglas não-ambíguas
        # NOTA: usa re.IGNORECASE para funcionar com texto original (não upper)
        siglas_seguras = [s for s in self.estados.keys() if s not in self.siglas_ambiguas]
        siglas_seguras_re = "|".join(siglas_seguras)
        match = re.search(
            rf'\b(?:em|no|na|de|do|da|pelo|pela|para\s+o|para\s+a)\s+({siglas_seguras_re})\b',
            texto,
            re.IGNORECASE
        )
        if match:
            return match.group(1).upper()

        # DF: detecção direta por sigla isolada (Distrito Federal nunca é ambíguo)
        if re.search(r'\bDF\b', texto.upper()):
            return "DF"

        return None

    def buscar_conteudo_artigo(self, url):
        """Camada 3: busca o HTML completo do artigo e extrai texto.

        Usado apenas quando as camadas anteriores não identificaram o estado.
        Segue redirecionamentos do Google News automaticamente.
        """
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            }
            response = requests.get(url, timeout=8, allow_redirects=True, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            textos = []
            for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "span"]):
                t = tag.get_text(separator=" ", strip=True)
                if len(t) > 20:
                    textos.append(t)

            return " ".join(textos[:80])
        except Exception as e:
            print(f"  ⚠️ Não foi possível buscar artigo: {e}")
            return ""

    def resolver_localizacao(self, titulo, descricao, link):
        """Encadeia as 3 camadas e retorna (cidade, estado).

        Cidade encontrada sempre confirma o estado — nunca retorna estado
        sem saber de qual cidade veio ou sem um padrão confiável de sigla.
        """
        texto_rss = f"{titulo} {descricao}"

        # Camada 1 — cidade confirma estado (texto do RSS)
        cidade, estado = self.detectar_localizacao(texto_rss)
        if estado:
            return cidade or "Não identificada", estado

        # Camada 1b — nome de estado por extenso (RSS)
        estado = self.detectar_estado_por_nome(texto_rss)
        if estado:
            return "Não identificada", estado

        # Camada 2 — sigla em padrão de contexto (RSS)
        sigla = self.detectar_sigla_contexto(texto_rss)
        if sigla:
            print(f"  📍 Sigla encontrada no RSS: {sigla}")
            return "Não identificada", sigla

        # Camada 3 — HTML completo do artigo
        print(f"  🌐 Buscando HTML do artigo...")
        conteudo = self.buscar_conteudo_artigo(link)
        if conteudo:
            cidade, estado = self.detectar_localizacao(conteudo)
            if estado:
                print(f"  📍 Cidade/estado no HTML: {cidade} / {estado}")
                time.sleep(0.4)
                return cidade or "Não identificada", estado

            estado = self.detectar_estado_por_nome(conteudo)
            if estado:
                print(f"  📍 Estado por nome no HTML: {estado}")
                time.sleep(0.4)
                return "Não identificada", estado

            sigla = self.detectar_sigla_contexto(conteudo)
            if sigla:
                print(f"  📍 Sigla no HTML: {sigla}")
                time.sleep(0.4)
                return "Não identificada", sigla

        return "Não identificada", "Não identificado"

    # ─── Detecção de cidade ───────────────────────────────────────────────────

    def detectar_cidade(self, titulo, descricao, estado, conteudo_extra=""):
        """Busca cidade no texto, confirmando com o estado já encontrado."""
        texto = f" {self.normalizar(titulo + ' ' + descricao + ' ' + conteudo_extra)} "
        cidades_ordenadas = sorted(self.cidade_estado.keys(), key=len, reverse=True)

        for cidade in cidades_ordenadas:
            if not self.cidade_permitida(cidade):
                continue
            uf = self.cidade_estado[cidade]
            if estado != "Não identificado" and uf != estado:
                continue
            if re.search(r"\b" + re.escape(cidade) + r"\b", texto):
                return self.formatar_cidade(cidade)

        return "Não identificada"

    def formatar_cidade(self, cidade):
        excecoes = {
            "sao paulo": "São Paulo",
            "sao jose do rio preto": "São José do Rio Preto",
            "ribeirao preto": "Ribeirão Preto",
            "jau": "Jaú",
            "bauru": "Bauru",
            "ibipora": "Ibiporã",
            "maringa": "Maringá",
            "londrina": "Londrina",
            "curitiba": "Curitiba",
            "tijucas": "Tijucas",
            "xanxere": "Xanxerê",
            "itajai": "Itajaí",
            "biguacu": "Biguaçu",
            "braco do norte": "Braço do Norte",
            "sao leopoldo": "São Leopoldo",
            "sapucaia do sul": "Sapucaia do Sul",
            "vitoria": "Vitória",
            "presidente kennedy": "Presidente Kennedy",
            "laranja da terra": "Laranja da Terra",
            "buzios": "Búzios",
            "rio largo": "Rio Largo",
            "brasilia": "Brasília",
            "belem": "Belém",
            "santarem": "Santarém",
            "maraba": "Marabá",
        }
        if cidade in excecoes:
            return excecoes[cidade]
        return " ".join(p.capitalize() for p in cidade.split())

    # ─── Busca principal ──────────────────────────────────────────────────────

    # Termos de exclusão adicionados a cada query para evitar conteúdo de astrologia
    EXCLUSOES_RSS = '-horóscopo -signo -zodíaco -astrologia -"mapa astral" -"previsão do dia" -nativo'

    def buscar_google_rss(self):
        print("🔍 Buscando Google News RSS...")

        for termo in self.termos:
            try:
                query = f"{termo} {self.EXCLUSOES_RSS}"
                url = (
                    "https://news.google.com/rss/search?"
                    f"q={quote(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
                )

                response = requests.get(url, timeout=20)
                response.raise_for_status()

                root = ET.fromstring(response.content)

                for item in root.findall(".//item")[:50]:
                    titulo = item.findtext("title", "").strip()
                    link = item.findtext("link", "").strip()
                    pub_date = item.findtext("pubDate", "").strip()
                    descricao = self.limpar_html(item.findtext("description", ""))

                    data = self.converter_data(pub_date)
                    if not data:
                        continue
                    if not titulo or not link:
                        continue
                    if not self.noticia_valida(titulo, descricao):
                        continue

                    # Cidade + estado em uma única resolução encadeada
                    cidade, estado = self.resolver_localizacao(titulo, descricao, link)

                    noticia = {
                        "id": self.gerar_id(titulo, link),
                        "titulo": titulo,
                        "descricao": descricao if descricao else titulo,
                        "link": link,
                        "data": data,
                        "tipo": "alerta",
                        "gravidade": self.detectar_gravidade(f"{titulo} {descricao}"),
                        "fonte": "Google News",
                        "estado": estado,
                        "cidade": cidade,
                        "termo_busca": termo
                    }

                    self.noticias.append(noticia)
                    print(f"✅ {data} | {estado} | {cidade} | {titulo[:80]}")

            except Exception as e:
                print(f"❌ Erro no termo '{termo}': {e}")

    # ─── Salvamento ───────────────────────────────────────────────────────────

    def salvar_noticias(self):
        existentes = self.carregar_existentes()

        ids_existentes = set()
        for n in existentes:
            n["id"] = self.gerar_id(n.get("titulo", ""), n.get("link", ""))
            ids_existentes.add(n["id"])

        novas = 0
        for noticia in self.noticias:
            if noticia["id"] not in ids_existentes:
                existentes.append(noticia)
                ids_existentes.add(noticia["id"])
                novas += 1

        def chave_data(n):
            try:
                return datetime.strptime(n.get("data", "01/01/1900"), "%d/%m/%Y")
            except:
                return datetime(1900, 1, 1)

        existentes.sort(key=chave_data, reverse=True)

        with open("noticias.json", "w", encoding="utf-8") as f:
            json.dump(existentes, f, ensure_ascii=False, indent=2)

        print(f"\n📰 Total salvo: {len(existentes)}")
        print(f"🆕 Novas notícias: {novas}")

    # ─── Execução ─────────────────────────────────────────────────────────────

    def executar(self):
        print("=" * 70)
        print("🦂 MONITOR DE ESCORPIÕES - BUSCA COM MUNICÍPIOS IBGE")
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        print("=" * 70)

        self.buscar_google_rss()
        self.salvar_noticias()

        print("=" * 70)
        print("✅ FINALIZADO")
        print("=" * 70)


if __name__ == "__main__":
    BuscadorNoticias().executar()
