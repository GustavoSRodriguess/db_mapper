#!/usr/bin/env python3
"""
Database Table Relationship Mapper - versão focada
Para bancos gigantes - mapeia apenas tabelas que interessam
"""

import streamlit as st
import pandas as pd
import json
import os
import time
from collections import defaultdict, deque
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import psycopg2
import pymysql
import sqlite3

# Configuração da página
st.set_page_config(
    page_title="Database Mapper - Focado",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

class FocusedDatabaseMapper:
    def __init__(self, db_type: str, connection_params: dict, patterns: list = None):
        self.db_type = db_type.lower()
        self.connection_params = connection_params
        self.patterns = patterns or ['pmact', 'wf', 'workflow', 'activity', 'process', 'user']
        self.relationships = defaultdict(list)
        self.reverse_relationships = defaultdict(list)
        self.table_columns = {}
        self.all_tables = set()
        self.cache_file = "path_cache.json"
        self.path_cache = self._load_cache()
        self.mapping_cache_file = "mapping_cache.json"
        self.mapping_cache = self._load_mapping_cache()
    
    def _load_cache(self):
        """Carrega o cache de caminhos do arquivo JSON"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            # Não mostrar warning na inicialização, só em debug
            print(f"Debug: Erro ao carregar cache: {e}")
        return {}
    
    def _save_cache(self):
        """Salva o cache de caminhos no arquivo JSON"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.path_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"❌ Erro ao salvar cache: {e}")
    
    def _get_cache_key(self, source: str, target: str, max_depth: int):
        """Gera chave única para o cache"""
        return f"{source}→{target}:{max_depth}"
    
    def _get_from_cache(self, source: str, target: str, max_depth: int):
        """Busca caminhos no cache"""
        cache_key = self._get_cache_key(source, target, max_depth)
        return self.path_cache.get(cache_key, None)
    
    def _save_to_cache(self, source: str, target: str, max_depth: int, paths: list):
        """Salva caminhos no cache"""
        cache_key = self._get_cache_key(source, target, max_depth)
        self.path_cache[cache_key] = {
            'paths': paths,
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'target': target,
            'max_depth': max_depth
        }
        self._save_cache()
    
    def get_cache_stats(self):
        """Retorna estatísticas do cache"""
        return {
            'total_searches': len(self.path_cache),
            'cache_size_mb': os.path.getsize(self.cache_file) / (1024*1024) if os.path.exists(self.cache_file) else 0,
            'oldest_search': min((entry['timestamp'] for entry in self.path_cache.values())) if self.path_cache else None,
            'newest_search': max((entry['timestamp'] for entry in self.path_cache.values())) if self.path_cache else None
        }
    
    def clear_cache(self):
        """Limpa todo o cache"""
        self.path_cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
    
    def _load_mapping_cache(self):
        """Carrega o cache de mapeamento do arquivo JSON"""
        try:
            if os.path.exists(self.mapping_cache_file):
                with open(self.mapping_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Debug: Erro ao carregar cache de mapeamento: {e}")
        return {}
    
    def _save_mapping_cache(self):
        """Salva o cache de mapeamento no arquivo JSON"""
        try:
            # Converter defaultdict para dict normal para serialização JSON
            cache_data = {
                'patterns': sorted(self.patterns),
                'db_info': f"{self.db_type}_{self.connection_params.get('database', 'unknown')}",
                'timestamp': datetime.now().isoformat(),
                'table_columns': dict(self.table_columns),
                'relationships': {k: list(v) for k, v in self.relationships.items()},
                'reverse_relationships': {k: list(v) for k, v in self.reverse_relationships.items()},
                'all_tables': list(self.all_tables),
                'total_tables': len(self.table_columns),
                'total_fks': sum(len(v) for v in self.relationships.values())
            }
            
            with open(self.mapping_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"❌ Erro ao salvar cache de mapeamento: {e}")
    
    def _load_from_mapping_cache(self):
        """Carrega dados do cache de mapeamento se compatível"""
        if not self.mapping_cache:
            return False
        
        try:
            # Verificar compatibilidade
            cached_patterns = set(self.mapping_cache.get('patterns', []))
            current_patterns = set(self.patterns)
            cached_db = self.mapping_cache.get('db_info', '')
            current_db = f"{self.db_type}_{self.connection_params.get('database', 'unknown')}"
            
            # Cache é compatível se os padrões atuais estão todos no cache
            # e o banco é o mesmo
            if not current_patterns.issubset(cached_patterns) or cached_db != current_db:
                return False
            
            # Carregar dados do cache
            self.table_columns = self.mapping_cache.get('table_columns', {})
            
            # Reconstruir defaultdict
            relationships_data = self.mapping_cache.get('relationships', {})
            self.relationships = defaultdict(list)
            for table, relations in relationships_data.items():
                self.relationships[table] = relations
            
            reverse_relationships_data = self.mapping_cache.get('reverse_relationships', {})
            self.reverse_relationships = defaultdict(list)
            for table, relations in reverse_relationships_data.items():
                self.reverse_relationships[table] = relations
            
            self.all_tables = set(self.mapping_cache.get('all_tables', []))
            
            return True
            
        except Exception as e:
            st.warning(f"⚠️ Erro ao carregar do cache de mapeamento: {e}")
            return False
    
    def get_mapping_cache_stats(self):
        """Retorna estatísticas do cache de mapeamento"""
        if not self.mapping_cache:
            return {'cached': False}
        
        return {
            'cached': True,
            'patterns': self.mapping_cache.get('patterns', []),
            'total_tables': self.mapping_cache.get('total_tables', 0),
            'total_fks': self.mapping_cache.get('total_fks', 0),
            'timestamp': self.mapping_cache.get('timestamp', ''),
            'db_info': self.mapping_cache.get('db_info', ''),
            'cache_size_mb': os.path.getsize(self.mapping_cache_file) / (1024*1024) if os.path.exists(self.mapping_cache_file) else 0
        }
    
    def clear_mapping_cache(self):
        """Limpa o cache de mapeamento"""
        self.mapping_cache = {}
        if os.path.exists(self.mapping_cache_file):
            os.remove(self.mapping_cache_file)
        
    def connect(self):
        """Conecta ao banco com timeout"""
        try:
            if self.db_type == 'postgresql':
                params = self.connection_params.copy()
                params.setdefault('connect_timeout', 10)
                return psycopg2.connect(**params)
            elif self.db_type == 'mysql':
                params = self.connection_params.copy()
                params.setdefault('connect_timeout', 10)
                return pymysql.connect(**params)
            elif self.db_type == 'sqlite':
                return sqlite3.connect(self.connection_params['database'], timeout=10)
        except Exception as e:
            raise Exception(f"Erro ao conectar: {e}")
    
    def get_relevant_tables(self, progress_callback=None):
        """Busca apenas tabelas que contenham os padrões especificados"""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            if progress_callback:
                progress_callback(10, "Buscando tabelas relevantes...")
            
            # Query para buscar tabelas por padrão
            if self.db_type == 'postgresql':
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
            elif self.db_type == 'mysql':
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                    ORDER BY table_name
                """)
            else:  # SQLite
                cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
            
            all_tables = [row[0] for row in cursor.fetchall()]
            
            # Filtrar tabelas relevantes
            relevant_tables = set()
            for table in all_tables:
                table_lower = table.lower()
                for pattern in self.patterns:
                    if pattern.lower() in table_lower:
                        relevant_tables.add(table)
                        break
            
            # Adicionar tabelas que referenciam ou são referenciadas pelas relevantes
            if progress_callback:
                progress_callback(20, f"Encontradas {len(relevant_tables)} tabelas relevantes. Expandindo rede...")
            
            # Buscar FKs que envolvem as tabelas relevantes
            if self.db_type == 'postgresql':
                placeholders = ','.join(['%s'] * len(relevant_tables))
                cursor.execute(f"""
                    SELECT DISTINCT tc.table_name, ccu.table_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.constraint_column_usage ccu 
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = 'public'
                        AND (tc.table_name IN ({placeholders}) OR ccu.table_name IN ({placeholders}))
                """, list(relevant_tables) * 2)
            elif self.db_type == 'mysql':
                placeholders = ','.join(['%s'] * len(relevant_tables))
                cursor.execute(f"""
                    SELECT DISTINCT kcu.table_name, kcu.referenced_table_name
                    FROM information_schema.key_column_usage kcu
                    WHERE kcu.referenced_table_name IS NOT NULL
                        AND kcu.table_schema = DATABASE()
                        AND (kcu.table_name IN ({placeholders}) OR kcu.referenced_table_name IN ({placeholders}))
                """, list(relevant_tables) * 2)
            
            # Expandir rede com tabelas conectadas
            for row in cursor.fetchall():
                relevant_tables.add(row[0])
                if row[1]:  # Pode ser None em alguns casos
                    relevant_tables.add(row[1])
            
            self.all_tables = relevant_tables
            
            if progress_callback:
                progress_callback(30, f"Rede expandida: {len(self.all_tables)} tabelas no escopo")
            
            return list(relevant_tables)
            
        finally:
            cursor.close()
            conn.close()
    
    def map_focused_relationships(self, progress_callback=None):
        """Mapeia relacionamentos apenas das tabelas relevantes com cache inteligente"""
        try:
            # 🚀 Primeiro, tentar carregar do cache
            if progress_callback:
                progress_callback(5, "Verificando cache de mapeamento...")
            
            if self._load_from_mapping_cache():
                if progress_callback:
                    progress_callback(100, f"✅ Carregado do cache! {len(self.table_columns)} tabelas")
                return True
            
            # Cache não compatível ou não existe, fazer mapeamento completo
            if progress_callback:
                progress_callback(10, "Cache não disponível - iniciando mapeamento...")
            
            # Primeiro, identificar tabelas relevantes
            relevant_tables = self.get_relevant_tables(progress_callback)
            
            if not relevant_tables:
                if progress_callback:
                    progress_callback(0, "❌ Nenhuma tabela relevante encontrada")
                return False
            
            conn = self.connect()
            cursor = conn.cursor()
            
            if progress_callback:
                progress_callback(40, f"Mapeando FKs de {len(relevant_tables)} tabelas...")
            
            # Mapear FKs apenas das tabelas relevantes
            if self.db_type == 'postgresql':
                placeholders = ','.join(['%s'] * len(relevant_tables))
                cursor.execute(f"""
                    SELECT 
                        tc.table_name as source_table,
                        kcu.column_name as source_column,
                        ccu.table_name as target_table,
                        ccu.column_name as target_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu 
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = 'public'
                        AND tc.table_name IN ({placeholders})
                """, relevant_tables)
            elif self.db_type == 'mysql':
                placeholders = ','.join(['%s'] * len(relevant_tables))
                cursor.execute(f"""
                    SELECT 
                        kcu.table_name as source_table,
                        kcu.column_name as source_column,
                        kcu.referenced_table_name as target_table,
                        kcu.referenced_column_name as target_column
                    FROM information_schema.key_column_usage kcu
                    WHERE kcu.referenced_table_name IS NOT NULL
                        AND kcu.table_schema = DATABASE()
                        AND kcu.table_name IN ({placeholders})
                """, relevant_tables)
            
            fk_count = 0
            for row in cursor.fetchall():
                source_table, source_column, target_table, target_column = row
                if source_table and target_table:
                    self.relationships[source_table].append((target_table, source_column, target_column))
                    self.reverse_relationships[target_table].append((source_table, target_column, source_column))
                    fk_count += 1
            
            if progress_callback:
                progress_callback(70, f"Processadas {fk_count} FKs. Mapeando colunas...")
            
            # Mapear colunas das tabelas relevantes
            if self.db_type == 'postgresql':
                cursor.execute(f"""
                    SELECT table_name, column_name, data_type
                    FROM information_schema.columns 
                    WHERE table_schema = 'public'
                        AND table_name IN ({placeholders})
                    ORDER BY table_name, ordinal_position
                """, relevant_tables)
            elif self.db_type == 'mysql':
                cursor.execute(f"""
                    SELECT table_name, column_name, data_type
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE()
                        AND table_name IN ({placeholders})
                    ORDER BY table_name, ordinal_position
                """, relevant_tables)
            
            for row in cursor.fetchall():
                table_name, column_name, data_type = row
                if table_name not in self.table_columns:
                    self.table_columns[table_name] = []
                self.table_columns[table_name].append({'name': column_name, 'type': data_type})
            
            cursor.close()
            conn.close()
            
            # 💾 Salvar no cache para futuras execuções
            if progress_callback:
                progress_callback(95, "Salvando no cache...")
            self._save_mapping_cache()
            
            if progress_callback:
                progress_callback(100, f"✅ Concluído! {len(self.table_columns)} tabelas, {fk_count} FKs")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"❌ Erro: {str(e)}")
            return False
    
    def find_path(self, source_table: str, target_table: str, max_depth: int = 5):
        """Busca caminhos entre tabelas com cache inteligente"""
        if source_table not in self.table_columns or target_table not in self.table_columns:
            return []
        
        if source_table == target_table:
            return [[source_table]]
        
        # 🚀 Primeiro, verificar se já existe no cache
        cached_result = self._get_from_cache(source_table, target_table, max_depth)
        if cached_result:
            return cached_result['paths']
        
        # Executar algoritmo de busca normal
        start_time = time.time()
        queue = deque([(source_table, [source_table])])
        visited = set()
        paths = []
        
        while queue and len(paths) < 10:
            current_table, path = queue.popleft()
            
            if len(path) > max_depth:
                continue
            
            if current_table in visited:
                continue
            visited.add(current_table)
            
            # Relacionamentos diretos
            for next_table, src_col, tgt_col in self.relationships.get(current_table, []):
                new_path = path + [f"--{src_col}-->{tgt_col}-->", next_table]
                
                if next_table == target_table:
                    paths.append(new_path)
                elif next_table not in visited and len(path) < max_depth:
                    queue.append((next_table, new_path))
            
            # Relacionamentos reversos
            for next_table, src_col, tgt_col in self.reverse_relationships.get(current_table, []):
                new_path = path + [f"<--{tgt_col}<--{src_col}--", next_table]
                
                if next_table == target_table:
                    paths.append(new_path)
                elif next_table not in visited and len(path) < max_depth:
                    queue.append((next_table, new_path))
        
        # 💾 Salvar resultado no cache para futuras consultas
        search_time = time.time() - start_time
        # Cache sempre para teste (depois pode voltar para > 0.1s)
        self._save_to_cache(source_table, target_table, max_depth, paths)
        
        return paths
    
    def search_tables(self, pattern: str):
        """Busca tabelas por padrão"""
        pattern = pattern.lower()
        matching = [table for table in self.table_columns.keys() 
                   if pattern in table.lower()]
        return sorted(matching)
    
    def get_table_info(self, table_name: str):
        """Informações da tabela"""
        if table_name not in self.table_columns:
            return None
        
        return {
            'columns': self.table_columns[table_name],
            'outbound_relations': self.relationships.get(table_name, []),
            'inbound_relations': self.reverse_relationships.get(table_name, [])
        }

def create_path_diagram(paths, source, target):
    """Cria diagrama dos caminhos"""
    if not paths:
        return None
    
    fig = go.Figure()
    colors = px.colors.qualitative.Set3
    
    for i, path in enumerate(paths[:5]):
        y_position = i * 2
        color = colors[i % len(colors)]
        
        table_names = [p for p in path if isinstance(p, str) and not ('-->' in p or '<--' in p)]
        x_positions = list(range(0, len(table_names) * 3, 3))
        
        # Linhas
        for j in range(len(x_positions) - 1):
            fig.add_trace(go.Scatter(
                x=[x_positions[j] + 1, x_positions[j + 1] - 1],
                y=[y_position, y_position],
                mode='lines',
                line=dict(color=color, width=2),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Nós
        fig.add_trace(go.Scatter(
            x=x_positions,
            y=[y_position] * len(x_positions),
            mode='markers+text',
            marker=dict(size=15, color=color, line=dict(color='black', width=1)),
            text=table_names,
            textposition='middle center',
            textfont=dict(color='black', size=8),
            name=f'Caminho {i+1}',
            hovertemplate='<b>%{text}</b><extra></extra>'
        ))
    
    fig.update_layout(
        title=f'{source} → {target}',
        showlegend=True,
        height=400,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='white'
    )
    
    return fig

def main():
    st.title("🎯 Database Mapper")
    st.markdown("*Mapeia apenas tabelas relevantes*")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuração")
        
        db_type = st.selectbox("Tipo", ["postgresql", "mysql", "sqlite"], index=0)
        
        if db_type != 'sqlite':
            host = st.text_input("Host", value="localhost")
            port = st.number_input("Porta", value=5432 if db_type == 'postgresql' else 3306)
            database = st.text_input("Database", value="dev")
            user = st.text_input("Usuário", value="postgres")
            password = st.text_input("Senha", type="password", value="")
        else:
            database = st.text_input("Arquivo", value="database.db")
            host = port = user = password = None
        
        st.markdown("---")
        st.subheader("🎯 Padrões de Tabelas")
        st.caption("Mapeia apenas tabelas que contenham estes padrões:")
        
        # Padrões personalizáveis
        default_patterns = "pmact,wf,workflow,activity,process,user,revision"
        patterns_text = st.text_area(
            "Padrões (separados por vírgula)", 
            value=default_patterns,
            help="Tabelas que contenham qualquer um destes padrões serão mapeadas"
        )
        
        patterns = [p.strip() for p in patterns_text.split(',') if p.strip()]
        
        st.info(f"🔍 Buscando: {', '.join(patterns)}")
        
        map_button = st.button("🎯 Mapear Focado", type="primary")
        
        st.markdown("---")
        st.subheader("🎯 Busca de Caminho")
        st.caption("Defina as tabelas para buscar caminhos:")
        
        source_table_input = st.text_input(
            "Tabela Origem", 
            value="pmactrevision",
            placeholder="Digite o nome da tabela origem",
            help="Nome da tabela de origem para buscar caminhos"
        )
        
        target_table_input = st.text_input(
            "Tabela Destino", 
            value="wfprocess",
            placeholder="Digite o nome da tabela destino", 
            help="Nome da tabela de destino para buscar caminhos"
        )
        
        st.markdown("---")
        st.subheader("💾 Cache de Caminhos")
        st.caption("Acelera consultas já realizadas:")
        
        # Mostrar estatísticas do cache se mapper existe
        if 'focused_mapper' in st.session_state and st.session_state.focused_mapper:
            cache_stats = st.session_state.focused_mapper.get_cache_stats()
            
            col_c1, col_c2 = st.columns(2)
            col_c1.metric("Buscas Salvas", cache_stats['total_searches'])
            col_c2.metric("Tamanho", f"{cache_stats['cache_size_mb']:.2f} MB")
            
            if st.button("🗑️ Limpar Cache", use_container_width=True):
                st.session_state.focused_mapper.clear_cache()
                st.success("✅ Cache limpo!")
                st.rerun()
        else:
            st.info("⏳ Cache disponível após mapeamento")
    
    # Inicializar mapper
    if 'focused_mapper' not in st.session_state:
        st.session_state.focused_mapper = None
    
    # Preparar conexão
    connection_params = {'database': database}
    if db_type != 'sqlite':
        if host: connection_params['host'] = host
        if port: connection_params['port'] = port
        if user: connection_params['user'] = user
        if password: connection_params['password'] = password
    
    # Executar mapeamento focado
    if map_button and database:
        st.session_state.focused_mapper = FocusedDatabaseMapper(db_type, connection_params, patterns)
        
        # Container de progresso
        progress_container = st.container()
        
        with progress_container:
            st.info("🎯 Executando mapeamento focado...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(percent, message):
                progress_bar.progress(percent / 100)
                status_text.text(message)
            
            # Executar
            success = st.session_state.focused_mapper.map_focused_relationships(update_progress)
            
            if success:
                st.success("✅ Mapeamento focado concluído!")
                time.sleep(1)
                progress_container.empty()
                st.rerun()
            else:
                st.error("❌ Erro no mapeamento focado")
                st.session_state.focused_mapper = None
    
    # Interface principal
    if not database:
        st.warning("⚠️ Configure a conexão na barra lateral")
        return
    
    if st.session_state.focused_mapper is None or not st.session_state.focused_mapper.table_columns:
        st.info("ℹ️ Clique em 'Mapear Focado' para começar")
        st.markdown("""
        **O que o mapeamento focado faz:**
        - 🎯 Mapeia apenas tabelas **relevantes**
        - 🔍 Encontra **tabela 1 → tabela 2** rapidamente
        """)
        return
    
    mapper = st.session_state.focused_mapper
    
    # Mostrar escopo
    st.success(f"✅ Mapeamento focado ativo: **{len(mapper.table_columns)} tabelas** mapeadas")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Encontrar Caminhos", "🔎 Explorar", "📊 Estatísticas", "💾 Cache"])
    
    with tab1:
        st.header("🔍 Encontrar Caminhos")
        
        # Usar os valores da barra lateral
        source_table = source_table_input.strip()
        target_table = target_table_input.strip()
        
        col1, col2, col3 = st.columns([4, 4, 2])
        
        with col1:
            st.info(f"**Origem:** {source_table}" if source_table else "⚠️ Digite a tabela origem na barra lateral")
            
            # Verificar se a tabela existe no escopo
            if source_table and source_table in mapper.table_columns:
                st.success("✅ Tabela encontrada no escopo")
            elif source_table:
                st.warning("⚠️ Tabela não encontrada - verifique o nome ou adicione padrões")
                
                # Sugerir tabelas similares
                similar = [t for t in mapper.table_columns.keys() 
                          if source_table.lower() in t.lower() or t.lower() in source_table.lower()]
                if similar:
                    st.caption(f"💡 Similares: {', '.join(similar[:3])}")
        
        with col2:
            st.info(f"**Destino:** {target_table}" if target_table else "⚠️ Digite a tabela destino na barra lateral")
            
            # Verificar se a tabela existe no escopo
            if target_table and target_table in mapper.table_columns:
                st.success("✅ Tabela encontrada no escopo")
            elif target_table:
                st.warning("⚠️ Tabela não encontrada - verifique o nome ou adicione padrões")
                
                # Sugerir tabelas similares
                similar = [t for t in mapper.table_columns.keys() 
                          if target_table.lower() in t.lower() or t.lower() in target_table.lower()]
                if similar:
                    st.caption(f"💡 Similares: {', '.join(similar[:3])}")
        
        with col3:
            max_depth = st.slider("Profundidade", 1, 6, 4)
        
        if st.button("🔍 Buscar Caminhos", type="primary", use_container_width=True):
            with st.spinner("Buscando..."):
                paths = mapper.find_path(source_table, target_table, max_depth)
            
            if paths:
                st.success(f"✅ Encontrados {len(paths)} caminhos!")
                
                # Diagrama
                fig = create_path_diagram(paths, source_table, target_table)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Detalhes
                for i, path in enumerate(paths, 1):
                    with st.expander(f"📍 Caminho {i}", expanded=i==1):
                        # Formatação mais limpa
                        clean_path = []
                        for item in path:
                            if isinstance(item, str) and not ('-->' in item or '<--' in item):
                                clean_path.append(f"**{item}**")
                            elif '-->' in item:
                                # Formato: --src_col-->tgt_col-->
                                # Extrair as colunas corretamente
                                clean_item = item.replace('--', ' ').replace('>', ' ')
                                parts = [p.strip() for p in clean_item.split() if p.strip()]
                                if len(parts) >= 2:
                                    src_col = parts[0]
                                    tgt_col = parts[1] 
                                    clean_path.append(f"→ `{src_col} → {tgt_col} →`")
                                else:
                                    # Fallback se não conseguir parsear
                                    clean_path.append(f"→ `{item}`")
                            elif '<--' in item:
                                # Formato: <--tgt_col<--src_col--
                                # Extrair as colunas corretamente
                                clean_item = item.replace('<--', ' ').replace('--', ' ')
                                parts = [p.strip() for p in clean_item.split() if p.strip()]
                                if len(parts) >= 2:
                                    tgt_col = parts[0]
                                    src_col = parts[1]
                                    clean_path.append(f"← `{tgt_col} ← {src_col} ← `")
                                else:
                                    # Fallback se não conseguir parsear
                                    clean_path.append(f"← `{item}`")
                        
                        st.markdown(" ".join(clean_path))
                        
                        # Mostrar tabelas intermediárias
                        tables_only = [item for item in path if isinstance(item, str) and not ('-->' in item or '<--' in item)]
                        if len(tables_only) > 2:
                            st.caption(f"Via: {' → '.join(tables_only[1:-1])}")
            else:
                st.warning("❌ Nenhum caminho encontrado")
                
                # Verificar se ambas as tabelas existem no escopo
                if source_table not in mapper.table_columns:
                    st.error(f"'{source_table}' não está no escopo mapeado")
                if target_table not in mapper.table_columns:
                    st.error(f"'{target_table}' não está no escopo mapeado")
                
                st.info("💡 Tente adicionar mais padrões na barra lateral e remapear")
    
    with tab2:
        st.header("🔎 Explorar Tabelas Mapeadas")
        
        # Mostrar todas as tabelas mapeadas
        st.subheader("📋 Tabelas no Escopo")
        
        cols = st.columns(4)
        for i, table in enumerate(sorted(mapper.table_columns.keys())):
            with cols[i % 4]:
                if st.button(table, key=f"explore_{i}"):
                    st.session_state.selected_table = table
        
        # Busca
        st.subheader("🔍 Buscar")
        search_pattern = st.text_input("Digite um padrão:", placeholder="revision, process, activity...")
        
        if search_pattern:
            results = mapper.search_tables(search_pattern)
            if results:
                st.success(f"✅ {len(results)} tabelas encontradas")
                for table in results:
                    if st.button(f"📋 {table}", key=f"search_{table}"):
                        st.session_state.selected_table = table
            else:
                st.warning("Nenhuma tabela encontrada")
        
        # Informações da tabela selecionada
        if hasattr(st.session_state, 'selected_table'):
            table = st.session_state.selected_table
            info = mapper.get_table_info(table)
            
            if info:
                st.markdown("---")
                st.subheader(f"📋 {table}")
                
                # Estatísticas rápidas
                col1, col2, col3 = st.columns(3)
                col1.metric("Colunas", len(info['columns']))
                col2.metric("FKs Saída", len(info['outbound_relations']))
                col3.metric("FKs Entrada", len(info['inbound_relations']))
                
                # Detalhes em tabs
                info_tab1, info_tab2, info_tab3 = st.tabs(["📊 Colunas", "➡️ Saída", "⬅️ Entrada"])
                
                with info_tab1:
                    df = pd.DataFrame(info['columns'])
                    st.dataframe(df, use_container_width=True)
                
                with info_tab2:
                    if info['outbound_relations']:
                        for target, src_col, tgt_col in info['outbound_relations']:
                            st.write(f"➡️ **{target}** (`{src_col}` → `{tgt_col}`)")
                    else:
                        st.info("Nenhuma FK de saída")
                
                with info_tab3:
                    if info['inbound_relations']:
                        for source, src_col, tgt_col in info['inbound_relations']:
                            st.write(f"⬅️ **{source}** (`{src_col}` ← `{tgt_col}`)")
                    else:
                        st.info("Nenhuma FK de entrada")
    
    with tab3:
        st.header("📊 Estatísticas do Escopo")
        
        total_tables = len(mapper.table_columns)
        total_fks = sum(len(v) for v in mapper.relationships.values())
        avg_conn = total_fks / total_tables if total_tables > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Tabelas Mapeadas", f"{total_tables:,}")
        col2.metric("Foreign Keys", f"{total_fks:,}")
        col3.metric("Conectividade Média", f"{avg_conn:.1f}")
        
        # Distribuição por padrão
        st.subheader("📈 Distribuição por Padrão")
        pattern_counts = {}
        for table in mapper.table_columns.keys():
            table_lower = table.lower()
            for pattern in patterns:
                if pattern.lower() in table_lower:
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
                    break
            else:
                pattern_counts['outros'] = pattern_counts.get('outros', 0) + 1
        
        df_patterns = pd.DataFrame(list(pattern_counts.items()), columns=['Padrão', 'Quantidade'])
        st.bar_chart(df_patterns.set_index('Padrão'))
        
        # Tabelas mais conectadas
        if mapper.table_columns:
            st.subheader("🔗 Mais Conectadas")
            connection_counts = {}
            for table in mapper.table_columns.keys():
                outbound = len(mapper.relationships.get(table, []))
                inbound = len(mapper.reverse_relationships.get(table, []))
                connection_counts[table] = outbound + inbound
            
            top_connected = sorted(connection_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            df_top = pd.DataFrame(top_connected, columns=['Tabela', 'Conexões'])
            st.bar_chart(df_top.set_index('Tabela'))
    
    with tab4:
        st.header("💾 Cache de Caminhos")
        
        cache_stats = mapper.get_cache_stats()
        
        # Métricas do cache
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Consultas Salvas", cache_stats['total_searches'])
        col2.metric("Tamanho do Cache", f"{cache_stats['cache_size_mb']:.2f} MB")
        col3.metric("Performance", "🚀 Instant" if cache_stats['total_searches'] > 0 else "⏳ Aguardando")
        col4.metric("Status", "✅ Ativo" if os.path.exists(mapper.cache_file) else "❌ Vazio")
        
        # Controles
        col_control1, col_control2 = st.columns(2)
        
        with col_control1:
            if st.button("🗑️ Limpar Todo o Cache", use_container_width=True):
                mapper.clear_cache()
                st.success("✅ Cache limpo com sucesso!")
                st.rerun()
        
        with col_control2:
            if st.button("♻️ Recarregar Cache", use_container_width=True):
                mapper.path_cache = mapper._load_cache()
                st.success("✅ Cache recarregado!")
        
        # Detalhes do cache
        if cache_stats['total_searches'] > 0:
            st.markdown("---")
            st.subheader("📋 Consultas em Cache")
            
            # Criar tabela com as consultas
            cache_data = []
            for key, entry in mapper.path_cache.items():
                # Parsear a chave para obter origem, destino e profundidade
                parts = key.split(':')
                if len(parts) == 2:
                    route_part = parts[0]
                    depth = parts[1]
                    
                    if '→' in route_part:
                        origem, destino = route_part.split('→')
                    else:
                        origem = destino = route_part
                    
                    # Calcular quantos caminhos foram encontrados
                    num_paths = len(entry['paths']) if entry['paths'] else 0
                    
                    # Formatear timestamp
                    timestamp = datetime.fromisoformat(entry['timestamp'])
                    formatted_time = timestamp.strftime("%d/%m/%Y %H:%M")
                    
                    cache_data.append({
                        'Origem': origem,
                        'Destino': destino,
                        'Profundidade': depth,
                        'Caminhos': num_paths,
                        'Data': formatted_time
                    })
            
            if cache_data:
                # Ordenar por data (mais recente primeiro)
                cache_data.sort(key=lambda x: x['Data'], reverse=True)
                
                df_cache = pd.DataFrame(cache_data)
                st.dataframe(df_cache, use_container_width=True)
                
                # Mostrar benefícios do cache
                st.markdown("---")
                st.subheader("🚀 Benefícios do Cache")
                
                benefit_col1, benefit_col2, benefit_col3 = st.columns(3)
                
                benefit_col1.success("""
                **⚡ Velocidade**
                - Consultas instantâneas
                - Sem acesso ao banco
                - Resposta < 1ms
                """)
                
                benefit_col2.info("""
                **💾 Eficiência**
                - Reduz carga no banco
                - Salva CPU e rede
                - Persistente entre sessões
                """)
                
                benefit_col3.warning("""
                **🔄 Inteligente**
                - Cache automático
                - Só salva buscas > 100ms
                - Gerenciamento transparente
                """)
                
            else:
                st.info("📭 Nenhuma consulta ainda foi salva no cache")
        else:
            st.info("📭 Cache vazio - Execute algumas buscas para popular o cache")
            st.markdown("""
            **Como o cache funciona:**
            
            1. 🔍 **Primeira busca**: Algoritmo completo + salva no cache
            2. 🚀 **Buscas seguintes**: Resultado instantâneo do cache  
            3. ⚡ **Performance**: De segundos para milissegundos
            4. 💾 **Persistente**: Cache mantido entre sessões
            5. 🧠 **Inteligente**: Só cacheia buscas que demoram > 100ms
            """)

if __name__ == "__main__":
    main()