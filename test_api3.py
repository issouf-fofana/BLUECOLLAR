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

# Obtenir le token d'accès
token_response = requests.post(token_url, data={
    'grant_type': 'client_credentials',
    'client_id': client_id,
    'client_secret': client_secret
})

if token_response.status_code == 200:
    access_token = token_response.json().get('access_token')
    
    # Tester la récupération du job le plus récent
    job_id = "1076124045"  # Job #1041241969
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    job_response = requests.get(f"{base_url}/v1/jobs/{job_id}?expand=notes,visits", headers=headers)
    
    if job_response.status_code == 200:
        job_data = job_response.json()
        
        print(f"🔍 Job ID: {job_data.get('id')}")
        print(f"🔍 Job Number: {job_data.get('number')}")
        print(f"🔍 Tech Notes Value: {repr(job_data.get('tech_notes'))}")
        print(f"🔍 Tech Notes Type: {type(job_data.get('tech_notes'))}")
        
        if job_data.get('tech_notes'):
            print(f"✅ SUCCESS! Tech Notes sont sauvegardées!")
            print(f"📝 Contenu: {job_data.get('tech_notes')[:200]}...")
        else:
            print("❌ Tech Notes toujours absentes")
            
    else:
        print(f"❌ Erreur: {job_response.status_code} - {job_response.text}")
        
else:
    print(f"❌ Erreur d'authentification: {token_response.status_code} - {token_response.text}")
