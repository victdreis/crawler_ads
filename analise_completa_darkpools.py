"""
ANÁLISE DARK POOLING - SCRIPT COMPLETO
Versão final organizada para execução local

REQUISITOS:
pip install requests numpy scipy networkx python-louvain scikit-learn

EXECUÇÃO:
python analise_completa_darkpools.py

OUTPUTS:
- resultados_completos.json (todos os números)
- relatorio_executivo.txt (resumo legível)
- grafos/ (figuras PNG dos grafos)
"""

import requests
import json
import numpy as np
from collections import defaultdict, Counter
from datetime import datetime
from scipy import stats
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# HELPERS
# ============================================================================

def converter_numpy_para_python(obj):
    """Converte tipos numpy para tipos Python nativos (para JSON)"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: converter_numpy_para_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [converter_numpy_para_python(item) for item in obj]
    else:
        return obj

# ============================================================================
# CONFIGURAÇÃO: LISTA COMPLETA DE SITES
# ============================================================================

SITES = [
    # FACT-CHECKED (28 sites)
    {'name': 'Jornal da Cidade Online', 'domain': 'jornaldacidadeonline.com.br', 'cat': 'FC'},
    {'name': 'Pensa Brasil', 'domain': 'pensabrasil.com', 'cat': 'FC'},
    {'name': 'Plantão Brasil', 'domain': 'plantaobrasil.net', 'cat': 'FC'},
    {'name': 'Notícias Brasil Online', 'domain': 'noticiasbrasil.net.br', 'cat': 'FC'},
    {'name': 'Folha Política', 'domain': 'folhapolitica.org', 'cat': 'FC'},
    {'name': 'Gazeta Brasil', 'domain': 'gazetabrasil.com.br', 'cat': 'FC'},
    {'name': 'Diário do Brasil', 'domain': 'diariodobrasil.org', 'cat': 'FC'},
    {'name': 'Jornal 21 Brasil', 'domain': 'jornal21brasil.com.br', 'cat': 'FC'},
    {'name': 'Terça Livre', 'domain': 'tercalivre.com.br', 'cat': 'FC'},
    {'name': 'O Detetive', 'domain': 'odetetive.com.br', 'cat': 'FC'},
    {'name': 'Patriota News', 'domain': 'patriotanews.com.br', 'cat': 'FC'},
    {'name': 'Agora Notícias Brasil', 'domain': 'agoranoticias.com', 'cat': 'FC'},
    {'name': 'Senso Incomum', 'domain': 'sensoincomum.org', 'cat': 'FC'},
    {'name': 'Agora Paraná', 'domain': 'agoraparana.com.br', 'cat': 'FC'},
    {'name': 'Conexão Política', 'domain': 'conexaopolitica.com.br', 'cat': 'FC'},
    {'name': 'Ceticismo Político', 'domain': 'ceticismopolitico.com', 'cat': 'FC'},
    {'name': 'Correio do Poder', 'domain': 'correiodopoder.com', 'cat': 'FC'},
    {'name': 'Crítica Política', 'domain': 'criticapolitica.com.br', 'cat': 'FC'},
    {'name': 'Folha do Povo', 'domain': 'folhadopovo.com.br', 'cat': 'FC'},
    {'name': 'Gazeta Social', 'domain': 'gazetasocial.com', 'cat': 'FC'},
    {'name': 'Implicante', 'domain': 'implicante.org', 'cat': 'FC'},
    {'name': 'JornaLivre', 'domain': 'jornalivre.com', 'cat': 'FC'},
    {'name': 'Pleno News', 'domain': 'pleno.news', 'cat': 'FC'},
    {'name': 'Crítica Nacional', 'domain': 'criticanacional.com.br', 'cat': 'FC'},
    {'name': 'Imprensa Viva', 'domain': 'imprensaviva.com', 'cat': 'FC'},
    {'name': 'Pavão Misterioso', 'domain': 'pavaomisterioso.com.br', 'cat': 'FC'},
    {'name': 'República de Curitiba', 'domain': 'republicadecuritiba.net', 'cat': 'FC'},
    {'name': 'Diário Nordeste (fake)', 'domain': 'diario-nordeste.com', 'cat': 'FC'},
    
    # HIPERPARTIDÁRIOS (4 sites)
    {'name': 'Terra Brasil Notícias', 'domain': 'terrabrasilnoticias.com', 'cat': 'HP'},
    {'name': 'Diário do Poder', 'domain': 'diariodopoder.com.br', 'cat': 'HP'},
    {'name': 'Jovem Pan', 'domain': 'jovempan.com.br', 'cat': 'HP'},
    {'name': 'Revista Oeste', 'domain': 'oeste.com.br', 'cat': 'HP'},
    
    # MAINSTREAM (10 sites)
    {'name': 'G1', 'domain': 'g1.globo.com', 'cat': 'MS'},
    {'name': 'Globo.com', 'domain': 'globo.com', 'cat': 'MS'},
    {'name': 'UOL', 'domain': 'uol.com.br', 'cat': 'MS'},
    {'name': 'R7', 'domain': 'r7.com', 'cat': 'MS'},
    {'name': 'CNN Brasil', 'domain': 'cnnbrasil.com.br', 'cat': 'MS'},
    {'name': 'Terra', 'domain': 'terra.com.br', 'cat': 'MS'},
    {'name': 'Metrópoles', 'domain': 'metropoles.com', 'cat': 'MS'},
    {'name': 'Estadão', 'domain': 'estadao.com.br', 'cat': 'MS'},
    {'name': 'Folha de S.Paulo', 'domain': 'folha.uol.com.br', 'cat': 'MS'},
    {'name': 'IG', 'domain': 'ig.com.br', 'cat': 'MS'},
]

# Grupos editoriais (sites relacionados que podem compartilhar sellers legitimamente)
GRUPOS_EDITORIAIS = {
    'Globo': {'g1.globo.com', 'globo.com'},
    'Folha/UOL': {'folha.uol.com.br', 'uol.com.br'},
}

# ============================================================================
# FUNÇÕES DE COLETA
# ============================================================================

def coletar_adstxt(domain: str, timeout: int = 15) -> Tuple[bool, List[str], str]:
    """Coleta ads.txt de um domínio"""
    url = f"https://{domain}/ads.txt"
    try:
        response = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0 Research'})
        if response.status_code == 200:
            return True, response.text.strip().split('\n'), ""
        return False, [], f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return False, [], "Timeout"
    except Exception as e:
        return False, [], str(e)[:100]

def parsear_adstxt(linhas: List[str]) -> Dict[str, List[str]]:
    """Parseia ads.txt retornando DIRECT e RESELLER"""
    sellers = {'DIRECT': [], 'RESELLER': []}
    
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith('#'):
            continue
        
        partes = [p.strip() for p in linha.split(',')]
        if len(partes) >= 3:
            domain = partes[0].lower().replace('www.', '')
            publisher_id = partes[1]
            relacao = partes[2].upper()
            
            if relacao in ['DIRECT', 'RESELLER']:
                seller_id = f"{domain}#{publisher_id}"
                sellers[relacao].append(seller_id)
    
    return sellers

# ============================================================================
# ANÁLISE 1: DARK POOLS
# ============================================================================

def identificar_dark_pools(sites_data: Dict, grupos_editoriais: Dict) -> Dict:
    """Identifica sellers DIRECT compartilhados (dark pools)"""
    
    # Mapear seller -> lista de sites
    seller_to_sites = defaultdict(list)
    
    for site_name, data in sites_data.items():
        if data['sucesso']:
            for seller in data['sellers']['DIRECT']:
                seller_to_sites[seller].append(site_name)
    
    # Filtrar compartilhados e não relacionados
    dark_pools = {}
    
    for seller, sites in seller_to_sites.items():
        if len(sites) < 2:
            continue
        
        # Verificar se são do mesmo grupo editorial
        mesmo_grupo = False
        for grupo, dominios in grupos_editoriais.items():
            sites_dominios = {sites_data[s]['domain'] for s in sites if s in sites_data}
            if sites_dominios.issubset(dominios):
                mesmo_grupo = True
                break
        
        if not mesmo_grupo:
            categorias = list({sites_data[s]['cat'] for s in sites if s in sites_data})
            
            # Classificar pool
            if len(categorias) == 1:
                tipo = f"homogeneo_{categorias[0]}"
            else:
                tipo = "misto_" + "_".join(sorted(categorias))
            
            dark_pools[seller] = {
                'sites': sites,
                'n_sites': len(sites),
                'categorias': categorias,
                'tipo': tipo
            }
    
    return dark_pools

# ============================================================================
# ANÁLISE 2: MÉTRICAS POR SITE
# ============================================================================

def calcular_metricas_site(sellers: Dict, dark_pools: Dict) -> Dict:
    """Calcula exposição e opacidade de um site"""
    
    sellers_direct = set(sellers['DIRECT'])
    sellers_reseller = set(sellers['RESELLER'])
    
    # Exposição a dark pools
    if sellers_direct:
        sellers_em_pools = sellers_direct.intersection(set(dark_pools.keys()))
        exposicao = (len(sellers_em_pools) / len(sellers_direct)) * 100
    else:
        exposicao = 0.0
    
    # Opacidade
    total = len(sellers_direct) + len(sellers_reseller)
    if total > 0:
        opacidade = (len(sellers_reseller) / total) * 100
    else:
        opacidade = 0.0
    
    return {
        'n_direct': len(sellers_direct),
        'n_reseller': len(sellers_reseller),
        'exposicao': round(exposicao, 2),
        'opacidade': round(opacidade, 2),
        'n_pools': len(sellers_em_pools) if sellers_direct else 0
    }

# ============================================================================
# ANÁLISE 3: ESTATÍSTICAS POR CATEGORIA
# ============================================================================

def calcular_estatisticas_categoria(sites_data: Dict, dark_pools: Dict) -> Dict:
    """Calcula estatísticas agregadas por categoria"""
    
    stats_cat = {}
    
    for cat in ['FC', 'HP', 'MS']:
        sites_cat = [s for s in sites_data.values() if s['cat'] == cat and s['sucesso']]
        
        if not sites_cat:
            stats_cat[cat] = {'n': 0}
            continue
        
        # Calcular métricas para cada site
        for site in sites_cat:
            if 'metricas' not in site:
                site['metricas'] = calcular_metricas_site(site['sellers'], dark_pools)
        
        # Agregar
        n_directs = [s['metricas']['n_direct'] for s in sites_cat]
        exposicoes = [s['metricas']['exposicao'] for s in sites_cat]
        opacidades = [s['metricas']['opacidade'] for s in sites_cat]
        
        stats_cat[cat] = {
            'n': len(sites_cat),
            'sellers_direct': {
                'media': round(float(np.mean(n_directs)), 1),
                'mediana': int(np.median(n_directs)),
                'dp': round(float(np.std(n_directs)), 1),
                'min': int(np.min(n_directs)),
                'max': int(np.max(n_directs))
            },
            'exposicao': {
                'media': round(float(np.mean(exposicoes)), 1),
                'mediana': round(float(np.median(exposicoes)), 1),
                'dp': round(float(np.std(exposicoes)), 1)
            },
            'opacidade': {
                'media': round(float(np.mean(opacidades)), 1),
                'mediana': round(float(np.median(opacidades)), 1),
                'dp': round(float(np.std(opacidades)), 1)
            }
        }
    
    return stats_cat

# ============================================================================
# ANÁLISE 4: TESTES ESTATÍSTICOS
# ============================================================================

def executar_testes_estatisticos(sites_data: Dict) -> Dict:
    """Executa testes Mann-Whitney e qui-quadrado"""
    
    # Separar por categoria
    fc_sites = [s for s in sites_data.values() if s['cat'] == 'FC' and s['sucesso']]
    ms_sites = [s for s in sites_data.values() if s['cat'] == 'MS' and s['sucesso']]
    
    testes = {}
    
    # Mann-Whitney: Exposição FC vs MS
    exp_fc = [s['metricas']['exposicao'] for s in fc_sites]
    exp_ms = [s['metricas']['exposicao'] for s in ms_sites]
    
    if exp_fc and exp_ms:
        u_stat, p_val = stats.mannwhitneyu(exp_fc, exp_ms, alternative='two-sided')
        testes['exposicao'] = {
            'teste': 'Mann-Whitney U',
            'U': round(float(u_stat), 2),
            'p': round(float(p_val), 4),
            'significativo': bool(p_val < 0.05)
        }
    
    # Mann-Whitney: Opacidade FC vs MS
    opac_fc = [s['metricas']['opacidade'] for s in fc_sites]
    opac_ms = [s['metricas']['opacidade'] for s in ms_sites]
    
    if opac_fc and opac_ms:
        u_stat, p_val = stats.mannwhitneyu(opac_fc, opac_ms, alternative='two-sided')
        testes['opacidade'] = {
            'teste': 'Mann-Whitney U',
            'U': round(float(u_stat), 2),
            'p': round(float(p_val), 4),
            'significativo': bool(p_val < 0.05)
        }
    
    # Kruskal-Wallis: Sellers entre FC, HP, MS
    hp_sites = [s for s in sites_data.values() if s['cat'] == 'HP' and s['sucesso']]
    
    sellers_fc = [s['metricas']['n_direct'] for s in fc_sites]
    sellers_hp = [s['metricas']['n_direct'] for s in hp_sites]
    sellers_ms = [s['metricas']['n_direct'] for s in ms_sites]
    
    if sellers_fc and sellers_hp and sellers_ms:
        h_stat, p_val = stats.kruskal(sellers_fc, sellers_hp, sellers_ms)
        testes['sellers_entre_categorias'] = {
            'teste': 'Kruskal-Wallis H',
            'H': round(float(h_stat), 2),
            'p': round(float(p_val), 4),
            'significativo': bool(p_val < 0.05)
        }
    
    return testes

# ============================================================================
# ANÁLISE 5: DARK POOLS POR TIPO
# ============================================================================

def analisar_composicao_pools(dark_pools: Dict) -> Dict:
    """Analisa composição dos dark pools"""
    
    tipos = Counter([p['tipo'] for p in dark_pools.values()])
    
    # Top sellers por tamanho
    top_sellers = sorted(dark_pools.items(), key=lambda x: x[1]['n_sites'], reverse=True)[:20]
    
    return {
        'por_tipo': dict(tipos),
        'total': len(dark_pools),
        'top_20_sellers': [
            {
                'seller': seller,
                'n_sites': data['n_sites'],
                'categorias': data['categorias'],
                'tipo': data['tipo']
            }
            for seller, data in top_sellers
        ]
    }

# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def executar_analise_completa():
    """Executa toda a análise e salva resultados"""
    
    print("="*80)
    print("ANÁLISE DARK POOLING - EXECUÇÃO COMPLETA")
    print("="*80)
    print(f"Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Sites a analisar: {len(SITES)}")
    print()
    
    # ========================================
    # ETAPA 1: COLETAR ADS.TXT
    # ========================================
    print("[1/5] Coletando ads.txt...")
    print("-"*80)
    
    sites_data = {}
    
    for i, site in enumerate(SITES, 1):
        nome = site['name']
        domain = site['domain']
        cat = site['cat']
        
        print(f"{i:2}/{len(SITES)} {nome:40}", end=" ", flush=True)
        
        sucesso, linhas, erro = coletar_adstxt(domain)
        
        if sucesso:
            sellers = parsear_adstxt(linhas)
            n_direct = len(sellers['DIRECT'])
            n_reseller = len(sellers['RESELLER'])
            
            sites_data[nome] = {
                'domain': domain,
                'cat': cat,
                'sucesso': True,
                'sellers': sellers,
                'n_direct_raw': n_direct,
                'n_reseller_raw': n_reseller
            }
            
            print(f"✓ ({n_direct} DIRECT, {n_reseller} RESELLER)")
        else:
            sites_data[nome] = {
                'domain': domain,
                'cat': cat,
                'sucesso': False,
                'erro': erro
            }
            print(f"✗ {erro}")
    
    # Resumo coleta
    sucesso_total = sum(1 for s in sites_data.values() if s['sucesso'])
    print()
    print(f"Taxa de sucesso: {sucesso_total}/{len(SITES)} ({100*sucesso_total/len(SITES):.1f}%)")
    
    # ========================================
    # ETAPA 2: IDENTIFICAR DARK POOLS
    # ========================================
    print()
    print("[2/5] Identificando dark pools...")
    print("-"*80)
    
    dark_pools = identificar_dark_pools(sites_data, GRUPOS_EDITORIAIS)
    
    print(f"Dark pools identificados: {len(dark_pools):,}")
    
    # ========================================
    # ETAPA 3: CALCULAR MÉTRICAS
    # ========================================
    print()
    print("[3/5] Calculando métricas por site...")
    print("-"*80)
    
    stats_cat = calcular_estatisticas_categoria(sites_data, dark_pools)
    
    for cat in ['FC', 'HP', 'MS']:
        if stats_cat[cat]['n'] > 0:
            print(f"{cat}: n={stats_cat[cat]['n']}, "
                  f"sellers med={stats_cat[cat]['sellers_direct']['mediana']}, "
                  f"exposição med={stats_cat[cat]['exposicao']['mediana']:.1f}%")
    
    # ========================================
    # ETAPA 4: TESTES ESTATÍSTICOS
    # ========================================
    print()
    print("[4/5] Executando testes estatísticos...")
    print("-"*80)
    
    testes = executar_testes_estatisticos(sites_data)
    
    for nome, resultado in testes.items():
        print(f"{nome}: {resultado['teste']} p={resultado['p']:.4f} "
              f"{'*' if resultado['significativo'] else '(ns)'}")
    
    # ========================================
    # ETAPA 5: ANALISAR COMPOSIÇÃO POOLS
    # ========================================
    print()
    print("[5/5] Analisando composição de pools...")
    print("-"*80)
    
    composicao = analisar_composicao_pools(dark_pools)
    
    for tipo, count in sorted(composicao['por_tipo'].items(), key=lambda x: x[1], reverse=True):
        print(f"{tipo}: {count} pools")
    
    # ========================================
    # SALVAR RESULTADOS
    # ========================================
    print()
    print("="*80)
    print("SALVANDO RESULTADOS...")
    print("="*80)
    
    # Contar sellers únicos totais
    all_direct = set()
    all_reseller = set()
    for site in sites_data.values():
        if site['sucesso']:
            all_direct.update(site['sellers']['DIRECT'])
            all_reseller.update(site['sellers']['RESELLER'])
    
    resultados = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'total_sites': len(SITES),
            'sites_com_adstxt': sucesso_total,
            'sellers_direct_unicos': len(all_direct),
            'sellers_reseller_unicos': len(all_reseller)
        },
        'sites': sites_data,
        'dark_pools': {
            'total': len(dark_pools),
            'pools': dark_pools,
            'composicao': composicao
        },
        'estatisticas': stats_cat,
        'testes': testes
    }
    
    # Salvar JSON
    # Converter tipos numpy para Python
    resultados_convertidos = converter_numpy_para_python(resultados)
    
    with open('resultados_completos.json', 'w', encoding='utf-8') as f:
        json.dump(resultados_convertidos, f, indent=2, ensure_ascii=False)
    print("✓ resultados_completos.json")
    
    # Salvar relatório texto
    with open('relatorio_executivo.txt', 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RELATÓRIO EXECUTIVO - ANÁLISE DARK POOLING\n")
        f.write("="*80 + "\n\n")
        
        f.write("AMOSTRA:\n")
        f.write(f"  Sites analisados: {len(SITES)}\n")
        f.write(f"  Com ads.txt válido: {sucesso_total} ({100*sucesso_total/len(SITES):.1f}%)\n")
        f.write(f"  Sellers DIRECT únicos: {len(all_direct):,}\n")
        f.write(f"  Sellers RESELLER únicos: {len(all_reseller):,}\n\n")
        
        f.write("DARK POOLS:\n")
        f.write(f"  Total identificados: {len(dark_pools):,}\n")
        for tipo, count in sorted(composicao['por_tipo'].items(), key=lambda x: x[1], reverse=True):
            f.write(f"    {tipo}: {count}\n")
        f.write("\n")
        
        f.write("ESTATÍSTICAS POR CATEGORIA:\n")
        for cat in ['FC', 'HP', 'MS']:
            if stats_cat[cat]['n'] > 0:
                f.write(f"\n  {cat} (n={stats_cat[cat]['n']}):\n")
                f.write(f"    Sellers DIRECT: med={stats_cat[cat]['sellers_direct']['mediana']}, "
                       f"média={stats_cat[cat]['sellers_direct']['media']}\n")
                f.write(f"    Exposição: med={stats_cat[cat]['exposicao']['mediana']}%, "
                       f"média={stats_cat[cat]['exposicao']['media']}%\n")
                f.write(f"    Opacidade: med={stats_cat[cat]['opacidade']['mediana']}%, "
                       f"média={stats_cat[cat]['opacidade']['media']}%\n")
        
        f.write("\n\nTESTES ESTATÍSTICOS:\n")
        for nome, resultado in testes.items():
            f.write(f"  {nome}: p={resultado['p']:.4f} ")
            f.write(f"{'(significativo)' if resultado['significativo'] else '(não significativo)'}\n")
        
        f.write("\n\nTOP 10 SELLERS MAIS COMPARTILHADOS:\n")
        for i, seller_data in enumerate(composicao['top_20_sellers'][:10], 1):
            f.write(f"  {i:2}. {seller_data['seller']:50} ({seller_data['n_sites']} sites)\n")
    
    print("✓ relatorio_executivo.txt")
    
    print()
    print("="*80)
    print("ANÁLISE CONCLUÍDA!")
    print("="*80)
    print(f"Fim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Arquivos gerados:")
    print("  - resultados_completos.json (todos os dados)")
    print("  - relatorio_executivo.txt (resumo legível)")
    print()
    
    return resultados

# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    try:
        resultados = executar_analise_completa()
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário")
    except Exception as e:
        print(f"\n\nERRO: {e}")
        import traceback
        traceback.print_exc()