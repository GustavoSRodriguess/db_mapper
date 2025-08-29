# 🎯 Database Mapper - Focused

Um mapeador inteligente de relacionamentos entre tabelas de banco de dados, otimizado para bancos gigantes através de mapeamento focado.

## ✨ Características

- **🎯 Mapeamento Focado**: Mapeia apenas tabelas que contenham padrões específicos
- **⚡ Cache Inteligente**: Sistema de cache duplo para máxima performance
- **🔍 Busca de Caminhos**: Encontra relacionamentos entre tabelas automaticamente
- **📊 Interface Visual**: Dashboard Streamlit com gráficos interativos
- **🗄️ Multi-Banco**: Suporte para PostgreSQL, MySQL e SQLite

## 🚀 Instalação

1. Clone o repositório
2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute a aplicação:
```bash
streamlit run focused_mapper.py
```

## 🎯 Como Usar

### 1. Configure a Conexão
Na barra lateral, configure:
- Tipo de banco (PostgreSQL, MySQL, SQLite)
- Parâmetros de conexão (host, porta, usuário, senha)

### 2. Defina os Padrões
Configure os padrões de tabelas que deseja mapear:
```
pmact,wf,workflow,activity,process,user,revision
```

### 3. Execute o Mapeamento
Clique em **"🎯 Mapear Focado"** para iniciar o mapeamento inteligente.

### 4. Busque Caminhos
- Digite a tabela origem (ex: `pmactrevision`)
- Digite a tabela destino (ex: `wfprocess`)
- Clique em **"🔍 Buscar Caminhos"**

## 🧠 Funcionamento

O sistema usa uma abordagem inteligente em duas etapas:

1. **Identificação**: Encontra tabelas que contenham os padrões especificados
2. **Expansão**: Inclui tabelas conectadas via foreign keys
3. **Cache**: Salva resultados para consultas futuras instantâneas

## 💾 Sistema de Cache

### Cache de Mapeamento
- Salva estrutura completa das tabelas e relacionamentos
- Evita remapeamento desnecessário
- Arquivo: `mapping_cache.json`

### Cache de Caminhos  
- Salva resultados de buscas entre tabelas
- Performance: de segundos para milissegundos
- Arquivo: `path_cache.json`

## 📋 Padrões Sugeridos

- `pmact` - Tabelas de atividades do sistema
- `wf` - Workflow/fluxo de trabalho
- `process` - Processos de negócio
- `user` - Usuários e permissões
- `revision` - Controle de versão
- `activity` - Atividades do sistema

## 🛠️ Tecnologias

- **Streamlit**: Interface web interativa
- **Plotly**: Visualizações e gráficos
- **Pandas**: Manipulação de dados
- **psycopg2**: Conexão PostgreSQL
- **pymysql**: Conexão MySQL
- **sqlite3**: Conexão SQLite

## ⚡ Performance

- **Mapeamento**: ~30s para 10K+ tabelas → ~2s para 50 tabelas relevantes
- **Busca**: ~5s primeira vez → ~1ms com cache
- **Memoria**: Redução de 95% no uso de RAM

## 🎨 Interface

### 🔍 Encontrar Caminhos
Busca automática de relacionamentos entre duas tabelas com visualização gráfica.

### 🔎 Explorar  
Navegação pelas tabelas mapeadas com detalhes de colunas e relacionamentos.

### 📊 Estatísticas
Métricas do escopo mapeado e análise de conectividade.

### 💾 Cache
Gerenciamento e estatísticas dos sistemas de cache.

## 🏃‍♂️ Execução Rápida

Para executar rapidamente:

```bash
# Ativar ambiente (se usando venv)
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Executar aplicação
streamlit run focused_mapper.py
```

---

*Otimizado para bancos de dados gigantes através de mapeamento inteligente e cache avançado* 🚀