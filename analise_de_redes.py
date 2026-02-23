"""
ANÁLISES DE REDE - COMPLEMENTO
Executa as 5 análises de rede descritas na metodologia

REQUISITOS ADICIONAIS:
pip install networkx python-louvain matplotlib

EXECUÇÃO:
1. Rode primeiro: python analise_completa_darkpools.py
2. Depois rode: python analises_de_rede.py

INPUT: resultados_completos.json
OUTPUT: resultados_redes.json + figuras PNG
"""

import json
import numpy as np
import networkx as nx
from networkx.algorithms import bipartite
import matplotlib.pyplot as plt
from collections import defaultdict
from scipy import stats

try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    print("AVISO: python-louvain não instalado. Modularidade será None")
    HAS_LOUVAIN = False

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

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
# CARREGAR RESULTADOS
# ============================================================================

def carregar_resultados():
    """Carrega resultados do script principal"""
    with open('resultados_completos.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# ============================================================================
# ANÁLISE 1: VULNERABILIDADE
# ============================================================================

def analisar_vulnerabilidade(G, sites_data):
    """Para cada SSP, quantos sites perderiam >50% sellers se SSP removido"""
    
    ssps = [n for n, d in G.nodes(data=True) if d.get('tipo') == 'ssp']
    sites = [n for n, d in G.nodes(data=True) if d.get('tipo') == 'site']
    
    vulnerabilidade = {}
    
    for ssp in ssps:
        vulneraveis_fc = []
        vulneraveis_ms = []
        
        for site in sites:
            if site not in G or site not in sites_data:
                continue
            
            # Total de sellers do site
            total_sellers = sites_data[site].get('n_direct_raw', 0)
            if total_sellers == 0:
                continue
            
            # Sellers deste SSP
            sellers_ssp = 0
            if G.has_edge(site, ssp):
                sellers_ssp = 1  # Simplificação: contamos 1 por aresta
            
            perda_percentual = sellers_ssp / total_sellers
            
            if perda_percentual > 0.5:
                cat = sites_data[site]['cat']
                if cat == 'FC':
                    vulneraveis_fc.append((site, perda_percentual))
                elif cat == 'MS':
                    vulneraveis_ms.append((site, perda_percentual))
        
        if vulneraveis_fc or vulneraveis_ms:
            vulnerabilidade[ssp] = {
                'n_vulneraveis_fc': len(vulneraveis_fc),
                'n_vulneraveis_ms': len(vulneraveis_ms),
                'taxa_fc': len(vulneraveis_fc) / len([s for s in sites if sites_data.get(s, {}).get('cat') == 'FC']) if sites else 0,
                'taxa_ms': len(vulneraveis_ms) / len([s for s in sites if sites_data.get(s, {}).get('cat') == 'MS']) if sites else 0
            }
    
    # Top SSPs por vulnerabilidade
    top_vuln = sorted(vulnerabilidade.items(), 
                     key=lambda x: x[1]['n_vulneraveis_fc'] + x[1]['n_vulneraveis_ms'], 
                     reverse=True)[:10]
    
    return {
        'completo': vulnerabilidade,
        'top_10': [{'ssp': ssp, **data} for ssp, data in top_vuln]
    }

# ============================================================================
# ANÁLISE 2: ESTRATÉGIAS (K-MEANS)
# ============================================================================

def analisar_estrategias(sites_data):
    """Clustering k-means sobre (DIRECT, RESELLER)"""
    
    # Preparar dados
    sites_validos = [(nome, data) for nome, data in sites_data.items() 
                     if data.get('sucesso') and 'metricas' in data]
    
    if len(sites_validos) < 10:
        return {'erro': 'Poucos sites para clustering'}
    
    X = np.array([[data['metricas']['n_direct'], 
                   data['metricas']['n_reseller']] 
                  for nome, data in sites_validos])
    
    nomes = [nome for nome, _ in sites_validos]
    categorias = [data['cat'] for _, data in sites_validos]
    
    # Normalizar
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # K-means com k=4
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=100)
    labels = kmeans.fit_predict(X_scaled)
    
    # Interpretar clusters
    clusters_info = {}
    for i in range(4):
        mask = labels == i
        sites_cluster = [nomes[j] for j in range(len(nomes)) if mask[j]]
        cats_cluster = [categorias[j] for j in range(len(categorias)) if mask[j]]
        
        clusters_info[f'cluster_{i}'] = {
            'n_sites': int(np.sum(mask)),
            'direct_medio': float(np.mean(X[mask, 0])),
            'reseller_medio': float(np.mean(X[mask, 1])),
            'categorias': dict(zip(*np.unique(cats_cluster, return_counts=True))),
            'sites': sites_cluster[:5]  # Primeiros 5 exemplos
        }
    
    # Teste qui-quadrado: clusters independentes de categorias?
    from scipy.stats import chi2_contingency
    
    contingencia = np.zeros((4, 3))  # 4 clusters × 3 categorias
    cat_map = {'FC': 0, 'HP': 1, 'MS': 2}
    
    for i in range(4):
        for j, cat in enumerate(['FC', 'HP', 'MS']):
            mask = (labels == i) & (np.array(categorias) == cat)
            contingencia[i, j] = np.sum(mask)
    
    chi2, p_val, dof, expected = chi2_contingency(contingencia)
    
    return {
        'clusters': clusters_info,
        'teste_independencia': {
            'chi2': float(chi2),
            'p': float(p_val),
            'significativo': bool(p_val < 0.05)
        }
    }

# ============================================================================
# ANÁLISE 3: BROKERS (BETWEENNESS)
# ============================================================================

def identificar_brokers(G, sites_data):
    """Calcula betweenness centrality dos SSPs"""
    
    # Betweenness de todos os nós
    bc = nx.betweenness_centrality(G, normalized=True)
    
    # Filtrar apenas SSPs
    bc_ssps = {node: bc[node] for node in G.nodes() 
               if G.nodes[node].get('tipo') == 'ssp'}
    
    # Top 10
    top_brokers = sorted(bc_ssps.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Para cada broker, contar sites FC e MS
    brokers_info = []
    for ssp, bc_value in top_brokers:
        vizinhos = list(G.neighbors(ssp))
        n_fc = sum(1 for v in vizinhos if sites_data.get(v, {}).get('cat') == 'FC')
        n_ms = sum(1 for v in vizinhos if sites_data.get(v, {}).get('cat') == 'MS')
        
        brokers_info.append({
            'ssp': ssp,
            'betweenness': float(bc_value),
            'n_sites_fc': n_fc,
            'n_sites_ms': n_ms,
            'total_sites': len(vizinhos),
            'is_broker': n_fc >= 2 and n_ms >= 2
        })
    
    # Contar brokers cross-editorial
    n_brokers = sum(1 for b in brokers_info if b['is_broker'])
    
    return {
        'top_10': brokers_info,
        'n_brokers_cross_editorial': n_brokers
    }

# ============================================================================
# ANÁLISE 4: INTEGRAÇÃO (ASSORTATIVITY + MODULARIDADE)
# ============================================================================

def analisar_integracao(G):
    """Calcula assortativity e modularidade no grafo de projeção"""
    
    # Criar grafo de projeção (sites conectados via SSPs)
    sites_nodes = {n for n, d in G.nodes(data=True) if d.get('tipo') == 'site'}
    G_proj = bipartite.weighted_projected_graph(G, sites_nodes)
    
    # Copiar atributo categoria
    for node in G_proj.nodes():
        if node in G:
            G_proj.nodes[node]['categoria'] = G.nodes[node].get('categoria', 'Unknown')
    
    # Assortativity
    try:
        assortativity = nx.attribute_assortativity_coefficient(G_proj, 'categoria')
    except:
        assortativity = None
    
    # Modularidade (Louvain)
    modularidade = None
    comunidades = None
    
    if HAS_LOUVAIN and len(G_proj.nodes()) > 0:
        try:
            partition = community_louvain.best_partition(G_proj)
            modularidade = community_louvain.modularity(partition, G_proj)
            
            # Analisar composição das comunidades
            comunidades_comp = defaultdict(lambda: {'FC': 0, 'HP': 0, 'MS': 0})
            
            for node, comm_id in partition.items():
                cat = G_proj.nodes[node].get('categoria', 'Unknown')
                if cat in ['FC', 'HP', 'MS']:
                    comunidades_comp[comm_id][cat] += 1
            
            comunidades = [
                {
                    'id': comm_id,
                    'composicao': dict(comp),
                    'tipo': 'mista' if len([c for c in comp.values() if c > 0]) > 1 else 'pura'
                }
                for comm_id, comp in comunidades_comp.items()
            ]
            
        except Exception as e:
            print(f"Erro ao calcular modularidade: {e}")
    
    return {
        'assortativity': float(assortativity) if assortativity is not None else None,
        'modularidade': float(modularidade) if modularidade is not None else None,
        'n_comunidades': len(comunidades) if comunidades else 0,
        'comunidades': comunidades if comunidades else []
    }

# ============================================================================
# CONSTRUIR GRAFO BIPARTIDO
# ============================================================================

def construir_grafo_bipartido(sites_data, dark_pools_data):
    """Constrói grafo bipartido sites-SSPs"""
    
    G = nx.Graph()
    
    # Adicionar nós de sites
    for nome, data in sites_data.items():
        if data.get('sucesso'):
            G.add_node(nome, 
                      bipartite=1, 
                      tipo='site', 
                      categoria=data['cat'])
    
    # Adicionar SSPs e arestas via dark pools
    pools = dark_pools_data['pools']
    
    for seller, pool_data in pools.items():
        ssp_domain = seller.split('#')[0]
        
        # Adicionar SSP se não existe
        if ssp_domain not in G:
            G.add_node(ssp_domain, bipartite=0, tipo='ssp')
        
        # Adicionar arestas
        for site in pool_data['sites']:
            if site in G:
                G.add_edge(site, ssp_domain, seller_id=seller)
    
    # Calcular propriedades básicas
    sites = [n for n, d in G.nodes(data=True) if d.get('tipo') == 'site']
    ssps = [n for n, d in G.nodes(data=True) if d.get('tipo') == 'ssp']
    
    densidade = len(G.edges()) / (len(sites) * len(ssps)) if sites and ssps else 0
    
    return G, {
        'n_sites': len(sites),
        'n_ssps': len(ssps),
        'n_arestas': len(G.edges()),
        'densidade': float(densidade)
    }

# ============================================================================
# PIPELINE PRINCIPAL
# ============================================================================

def executar_analises_rede():
    """Executa todas as 5 análises de rede"""
    
    print("="*80)
    print("ANÁLISES DE REDE")
    print("="*80)
    print()
    
    # Carregar resultados
    print("[1/6] Carregando resultados...")
    resultados = carregar_resultados()
    sites_data = resultados['sites']
    dark_pools_data = resultados['dark_pools']
    
    # Construir grafo
    print("[2/6] Construindo grafo bipartido...")
    G, props_grafo = construir_grafo_bipartido(sites_data, dark_pools_data)
    print(f"  Nós: {props_grafo['n_sites']} sites + {props_grafo['n_ssps']} SSPs")
    print(f"  Arestas: {props_grafo['n_arestas']}")
    print(f"  Densidade: {props_grafo['densidade']:.4f}")
    
    # Análises
    print("\n[3/6] Análise 1: Vulnerabilidade...")
    vulnerabilidade = analisar_vulnerabilidade(G, sites_data)
    print(f"  Top SSP vulnerável: {vulnerabilidade['top_10'][0]['ssp'] if vulnerabilidade['top_10'] else 'N/A'}")
    
    print("\n[4/6] Análise 2: Estratégias (K-means)...")
    estrategias = analisar_estrategias(sites_data)
    if 'clusters' in estrategias:
        print(f"  4 clusters identificados")
        print(f"  Qui-quadrado p={estrategias['teste_independencia']['p']:.4f}")
    
    print("\n[5/6] Análise 3: Brokers...")
    brokers = identificar_brokers(G, sites_data)
    print(f"  Top broker: {brokers['top_10'][0]['ssp']} (BC={brokers['top_10'][0]['betweenness']:.4f})")
    print(f"  Brokers cross-editorial: {brokers['n_brokers_cross_editorial']}")
    
    print("\n[6/6] Análise 4: Integração...")
    integracao = analisar_integracao(G)
    print(f"  Assortativity: {integracao['assortativity']:.4f}" if integracao['assortativity'] else "  Assortativity: N/A")
    print(f"  Modularidade: {integracao['modularidade']:.4f}" if integracao['modularidade'] else "  Modularidade: N/A")
    print(f"  Comunidades: {integracao['n_comunidades']}")
    
    # Salvar resultados
    print()
    print("="*80)
    print("SALVANDO RESULTADOS DE REDE...")
    print("="*80)
    
    resultados_rede = {
        'grafo': props_grafo,
        'vulnerabilidade': vulnerabilidade,
        'estrategias': estrategias,
        'brokers': brokers,
        'integracao': integracao
    }
    
    # Converter tipos numpy para Python
    resultados_rede_convertidos = converter_numpy_para_python(resultados_rede)
    
    with open('resultados_redes.json', 'w', encoding='utf-8') as f:
        json.dump(resultados_rede_convertidos, f, indent=2, ensure_ascii=False)
    
    print("✓ resultados_redes.json")
    print()
    print("CONCLUÍDO!")
    
    return resultados_rede

# ============================================================================
# EXECUÇÃO
# ============================================================================

if __name__ == "__main__":
    try:
        import os
        if not os.path.exists('resultados_completos.json'):
            print("ERRO: Execute primeiro 'python analise_completa_darkpools.py'")
        else:
            resultados_rede = executar_analises_rede()
    except Exception as e:
        print(f"\n\nERRO: {e}")
        import traceback
        traceback.print_exc()