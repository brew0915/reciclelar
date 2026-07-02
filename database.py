import streamlit as st
from sqlalchemy import create_engine

# ==============================================================================
# CONFIGURAÇÃO DO ENGINE DO SQLALCHEMY (PRODUÇÃO / STREAMLIT CLOUD)
# ==============================================================================
# Lê de forma segura a URL de conexão configurada nos Secrets do Streamlit
DATABASE_URL = st.secrets["DATABASE_URL"]

# Criando o engine com gerenciamento robusto de conexões (Connection Pool)
engine = create_engine(
    DATABASE_URL,
    # 1. PRE-PING (Crucial para Nuvem):
    # Testa a conexão silenciosamente antes de cada execução. Se o banco (Supabase/Neon)
    # tiver derrubado o canal por inatividade, o SQLAlchemy recria a conexão automaticamente.
    pool_pre_ping=True,
    
    # 2. TAMANHO DO POOL:
    # Mantém até 5 conexões ativas persistentes para reaproveitamento rápido.
    pool_size=5,
    
    # 3. TRANSBORDAMENTO (OVERFLOW):
    # Permite abrir até 10 conexões extras temporárias se houver pico de usuários acessando ao mesmo tempo.
    max_overflow=10,
    
    # 4. RECICLAGEM DE CONEXÕES:
    # Fecha e recria conexões que estão abertas há mais de 15 minutos (900 segundos).
    # Impede obsolescência induzida por firewalls ou timeouts do servidor de banco.
    pool_recycle=900,
    
    # 5. TIMEOUT:
    # Limita o tempo máximo de espera por uma conexão livre no pool a 30 segundos antes de disparar erro.
    pool_timeout=30
)
