import hashlib
import streamlit as st

st.cache_data.clear()

# senha e hash fornecidos
senha = 'gui38198$Uno'
hash_fornecido = '9b5972cede761cf50c08dd1b641b5d0d'

# Testando com MD5
hash_md5 = hashlib.md5(senha.encode()).hexdigest()
print('MD5:', hash_md5 == hash_fornecido)

# Testando com SHA-1
hash_sha1 = hashlib.sha1(senha.encode()).hexdigest()
print('SHA-1:', hash_sha1 == hash_fornecido)

# Testando com SHA-256
hash_sha256 = hashlib.sha256(senha.encode()).hexdigest()
print('SHA-256:', hash_sha256 == hash_fornecido)







