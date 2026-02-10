import requests
import urllib3
from collections import defaultdict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def analyze_site(domain):
    """Analisa ads.txt de um site"""
    url = f"https://{domain}/ads.txt"
    
    try:
        response = requests.get(
            url, 
            timeout=10, 
            verify=False,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        if response.status_code == 200:
            lines = response.text.split('\n')
            direct_sellers = []
            
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    parts = line.split(',')
                    if len(parts) >= 3 and 'DIRECT' in parts[2].upper():
                        direct_sellers.append({
                            'ad_system': parts[0].strip(),
                            'seller_id': parts[1].strip()
                        })
            
            return direct_sellers
            
    except Exception as e:
        pass
        
    return []

# ============================================================
# CONFIGURAÇÃO
# ============================================================

sites_legitimos = [
    ("UOL", "uol.com.br"),
    ("R7", "r7.com"),
    ("Terra", "terra.com.br"),
    ("IG", "ig.com.br"),
]

sites_investigacao = [
    ("Jornal da Cidade Online", "jornaldacidadeonline.com.br"),
    ("Brasil Sem Medo", "brasilsemmedo.com"),
    ("Conexão Política", "conexaopolitica.com.br"),
]

# MARCAS IDENTIFICADAS NA ANÁLISE HTML
marcas_identificadas = {
    'sites_legitimos': ['C&A', 'Samsung', 'LG', 'Apple', 'Tim', 'Vivo', 'Claro', 'Oi', 'Caixa', 'Inter'],
    'sites_suspeitos': ['LG', 'Apple', 'Tim', 'Vivo', 'Oi', 'Inter'],
    'compartilhadas': ['LG', 'Apple', 'Tim', 'Vivo', 'Oi', 'Inter']
}

# ============================================================
# COLETA
# ============================================================

print("\n🔍 COLETANDO DADOS...\n")

legitimate_results = {}
for nome, domain in sites_legitimos:
    print(f"   Analisando {nome}...", end=" ")
    ids = analyze_site(domain)
    if ids:
        legitimate_results[domain] = ids
        print(f"✓ ({len(ids)} IDs)")
    else:
        print("✗")

suspect_results = {}
for nome, domain in sites_investigacao:
    print(f"   Analisando {nome}...", end=" ")
    ids = analyze_site(domain)
    if ids:
        suspect_results[domain] = ids
        print(f"✓ ({len(ids)} IDs)")
    else:
        print("✗")

# ============================================================
# ANÁLISE DETALHADA DE DARK POOLS
# ============================================================

if legitimate_results and suspect_results:
    # Cria mapa completo
    id_usage = defaultdict(lambda: {'legit': [], 'suspect': []})
    
    for domain, ids in legitimate_results.items():
        for id_info in ids:
            key = f"{id_info['ad_system']}|{id_info['seller_id']}"
            id_usage[key]['legit'].append(domain)
    
    for domain, ids in suspect_results.items():
        for id_info in ids:
            key = f"{id_info['ad_system']}|{id_info['seller_id']}"
            id_usage[key]['suspect'].append(domain)
    
    dark_pools = {k: v for k, v in id_usage.items() 
                  if v['legit'] and v['suspect']}
    
    # ============================================================
    # VISUALIZAÇÃO DETALHADA
    # ============================================================
    
    print("\n" + "="*70)
    print("🚨 DARK POOLS IDENTIFICADOS - LISTA COMPLETA")
    print("="*70)
    
    if dark_pools:
        # Agrupa por rede de anúncios
        pools_by_network = defaultdict(list)
        for seller_id, usage in dark_pools.items():
            ad_system, sid = seller_id.split('|', 1)
            pools_by_network[ad_system].append((sid, usage))
        
        # Mostra por rede
        for network in sorted(pools_by_network.keys()):
            pools_list = pools_by_network[network]
            print(f"\n📡 REDE: {network}")
            print(f"   Dark Pools nesta rede: {len(pools_list)}")
            print("   " + "-"*66)
            
            for i, (sid, usage) in enumerate(pools_list, 1):
                print(f"\n   {i}. Seller ID: {sid}")
                print(f"      Compartilhado entre:")
                
                # Sites legítimos
                print(f"      ✅ Sites Legítimos ({len(usage['legit'])}):")
                for site in usage['legit']:
                    site_name = next((nome for nome, dom in sites_legitimos if dom == site), site)
                    print(f"         • {site_name}")
                
                # Sites suspeitos
                print(f"      ⚠️  Sites Suspeitos ({len(usage['suspect'])}):")
                for site in usage['suspect']:
                    site_name = next((nome for nome, dom in sites_investigacao if dom == site), site)
                    print(f"         • {site_name}")
        
        # ============================================================
        # 🆕 MARCAS IDENTIFICADAS (NOVA SEÇÃO)
        # ============================================================
        
        print("\n\n" + "="*70)
        print("🏢 MARCAS IDENTIFICADAS NOS ANÚNCIOS")
        print("="*70)
        
        print("\n📊 RESUMO DA ANÁLISE HTML:")
        print(f"   Período: Dezembro 2024")
        print(f"   Método: Análise de código HTML e capturas automatizadas")
        
        print("\n✅ Marcas em Sites Legítimos:")
        print(f"   {', '.join(marcas_identificadas['sites_legitimos'])}")
        
        print("\n⚠️  Marcas em Sites de Desinformação:")
        print(f"   {', '.join(marcas_identificadas['sites_suspeitos'])}")
        
        print("\n🚨 MARCAS COMPARTILHADAS (Evidência de Dark Pooling):")
        for marca in marcas_identificadas['compartilhadas']:
            print(f"   💰 {marca}")
        
        print("\n📝 IMPLICAÇÃO:")
        print("   Estas marcas aparecem TANTO em sites legítimos quanto em sites")
        print("   de desinformação, indicando que inadvertidamente financiam fake")
        print("   news através de dark pooling em redes como Google DoubleClick.")
        
        # ============================================================
        # ANÁLISE POR SITE SUSPEITO
        # ============================================================
        
        print("\n\n" + "="*70)
        print("📊 ANÁLISE POR SITE SUSPEITO")
        print("="*70)
        
        for nome, domain in sites_investigacao:
            if domain in suspect_results:
                # Conta quantos IDs deste site estão em dark pools
                site_darkpool_count = 0
                darkpool_details = []
                
                for id_info in suspect_results[domain]:
                    key = f"{id_info['ad_system']}|{id_info['seller_id']}"
                    if key in dark_pools:
                        site_darkpool_count += 1
                        darkpool_details.append({
                            'network': id_info['ad_system'],
                            'id': id_info['seller_id'],
                            'shared_with': dark_pools[key]['legit']
                        })
                
                total_ids = len(suspect_results[domain])
                percentage = (site_darkpool_count / total_ids * 100) if total_ids > 0 else 0
                
                print(f"\n⚠️  {nome}")
                print(f"   Domain: {domain}")
                print(f"   Total de Seller IDs: {total_ids}")
                print(f"   IDs em Dark Pools: {site_darkpool_count} ({percentage:.1f}%)")
                
                if darkpool_details:
                    print(f"   \n   Detalhes dos Dark Pools:")
                    for detail in darkpool_details[:5]:  # Mostra primeiros 5
                        print(f"      • {detail['network']}: {detail['id']}")
                        print(f"        Compartilhado com: {', '.join([next((n for n,d in sites_legitimos if d==s), s) for s in detail['shared_with']])}")
                    
                    if len(darkpool_details) > 5:
                        print(f"      ... e mais {len(darkpool_details) - 5} dark pools")
        
        # ============================================================
        # TOP REDES DE ANÚNCIOS EM DARK POOLS
        # ============================================================
        
        print("\n\n" + "="*70)
        print("🏆 TOP REDES DE ANÚNCIOS EM DARK POOLS")
        print("="*70 + "\n")
        
        network_counts = defaultdict(int)
        for seller_id in dark_pools.keys():
            ad_system, _ = seller_id.split('|', 1)
            network_counts[ad_system] += 1
        
        top_networks = sorted(network_counts.items(), key=lambda x: x[1], reverse=True)
        
        for i, (network, count) in enumerate(top_networks, 1):
            percentage = (count / len(dark_pools) * 100)
            bar = "█" * int(percentage / 2)
            print(f"{i:2d}. {network:30s} │{bar:50s}│ {count:3d} ({percentage:5.1f}%)")
        
        # ============================================================
        # ESTATÍSTICAS FINAIS
        # ============================================================
        
        print("\n" + "="*70)
        print("📈 ESTATÍSTICAS FINAIS")
        print("="*70)
        print(f"Total de seller IDs únicos analisados:     {len(id_usage)}")
        print(f"Dark pools identificados:                  {len(dark_pools)} ({len(dark_pools)/len(id_usage)*100:.1f}%)")
        print(f"Sites legítimos analisados:                {len(legitimate_results)}")
        print(f"Sites suspeitos analisados:                {len(suspect_results)}")
        print(f"Redes de anúncios envolvidas em dark pools: {len(pools_by_network)}")
        print(f"Marcas compartilhadas identificadas:       {len(marcas_identificadas['compartilhadas'])}")
        
        # ============================================================
        # EXPORTAR PARA CSV
        # ============================================================
        
        print("\n" + "="*70)
        print("💾 EXPORTANDO DADOS")
        print("="*70 + "\n")
        
        # CSV dos dark pools
        with open('dark_pools_brasil.csv', 'w', encoding='utf-8') as f:
            f.write("Rede,Seller_ID,Sites_Legitimos,Sites_Suspeitos\n")
            for seller_id, usage in dark_pools.items():
                ad_system, sid = seller_id.split('|', 1)
                legit_sites = ';'.join(usage['legit'])
                suspect_sites = ';'.join(usage['suspect'])
                f.write(f'"{ad_system}","{sid}","{legit_sites}","{suspect_sites}"\n')
        
        print("✓ Arquivo criado: dark_pools_brasil.csv")
        
        # Relatório detalhado em TXT
        with open('relatorio_dark_pools.txt', 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("RELATÓRIO DE DARK POOLS - BRASIL\n")
            f.write("="*70 + "\n\n")
            
            # Adiciona seção de marcas
            f.write("MARCAS IDENTIFICADAS NOS ANÚNCIOS\n")
            f.write("-"*70 + "\n\n")
            f.write("Sites Legítimos:\n")
            f.write(f"  {', '.join(marcas_identificadas['sites_legitimos'])}\n\n")
            f.write("Sites de Desinformação:\n")
            f.write(f"  {', '.join(marcas_identificadas['sites_suspeitos'])}\n\n")
            f.write("⚠️ MARCAS COMPARTILHADAS (Dark Pooling):\n")
            for marca in marcas_identificadas['compartilhadas']:
                f.write(f"  • {marca}\n")
            f.write("\nEstas marcas financiam inadvertidamente fake news.\n\n")
            f.write("="*70 + "\n\n")
            
            for network in sorted(pools_by_network.keys()):
                pools_list = pools_by_network[network]
                f.write(f"\nREDE: {network}\n")
                f.write(f"Dark Pools: {len(pools_list)}\n")
                f.write("-"*70 + "\n")
                
                for sid, usage in pools_list:
                    f.write(f"\nSeller ID: {sid}\n")
                    f.write(f"  Sites Legítimos:\n")
                    for site in usage['legit']:
                        f.write(f"    - {site}\n")
                    f.write(f"  Sites Suspeitos:\n")
                    for site in usage['suspect']:
                        f.write(f"    - {site}\n")
        
        print("✓ Arquivo criado: relatorio_dark_pools.txt")
        
        # 🆕 CSV das marcas
        with open('marcas_identificadas.csv', 'w', encoding='utf-8') as f:
            f.write("Marca,Sites_Legitimos,Sites_Suspeitos,Dark_Pooling\n")
            for marca in marcas_identificadas['compartilhadas']:
                f.write(f'"{marca}","Sim","Sim","SIM"\n')
            
            # Marcas apenas em legítimos
            marcas_apenas_legit = set(marcas_identificadas['sites_legitimos']) - set(marcas_identificadas['compartilhadas'])
            for marca in marcas_apenas_legit:
                f.write(f'"{marca}","Sim","Não","NÃO"\n')
        
        print("✓ Arquivo criado: marcas_identificadas.csv")
        
        print("\n" + "="*70)
        print("✅ ANÁLISE CONCLUÍDA")
        print("="*70 + "\n")

else:
    print("⚠️  Dados insuficientes para análise")