#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration Service Fusion
client_id = os.getenv('SERVICE_FUSION_CLIENT_ID')
client_secret = os.getenv('SERVICE_FUSION_CLIENT_SECRET')
token_url = os.getenv('SERVICE_FUSION_TOKEN_URL', 'https://api.servicefusion.com/oauth/access_token')
base_url = os.getenv('SERVICE_FUSION_BASE_URL', 'https://api.servicefusion.com')

print(f"🔑 Client ID: {client_id[:10]}...")
print(f"🔑 Token URL: {token_url}")

# Obtenir le token d'accès
print("\n🔐 Obtention du token d'accès...")
token_response = requests.post(token_url, data={
    'grant_type': 'client_credentials',
    'client_id': client_id,
    'client_secret': client_secret
})

if token_response.status_code == 200:
    access_token = token_response.json().get('access_token')
    print(f"✅ Token obtenu: {access_token[:20]}...")
    
    # Tester la récupération d'un job
    job_id = "1076123987"  # Job récent
    print(f"\n🔍 Test de récupération du job {job_id}...")
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    job_response = requests.get(f"{base_url}/v1/jobs/{job_id}?expand=notes,visits", headers=headers)
    
    print(f"📊 Status Code: {job_response.status_code}")
    print(f"📊 Headers: {dict(job_response.headers)}")
    
    if job_response.status_code == 200:
        job_data = job_response.json()
        print(f"📊 Job Data Keys: {list(job_data.keys())}")
        
        if 'tech_notes' in job_data:
            print(f"✅ Tech Notes trouvées: {job_data['tech_notes'][:100]}...")
        else:
            print("❌ Tech Notes non trouvées dans la réponse GET")
            print(f"📊 Champs disponibles: {list(job_data.keys())}")
    else:
        print(f"❌ Erreur: {job_response.text}")
        
else:
    print(f"❌ Erreur d'authentification: {token_response.status_code} - {token_response.text}")
