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
    
    # Tester la récupération d'un job
    job_id = "1076123987"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    job_response = requests.get(f"{base_url}/v1/jobs/{job_id}?expand=notes,visits", headers=headers)
    
    if job_response.status_code == 200:
        job_data = job_response.json()
        
        print(f"🔍 Tech Notes Value: {repr(job_data.get('tech_notes'))}")
        print(f"🔍 Tech Notes Type: {type(job_data.get('tech_notes'))}")
        print(f"🔍 Completion Notes: {repr(job_data.get('completion_notes'))}")
        print(f"🔍 Description: {repr(job_data.get('description')[:100])}")
        
        # Vérifier tous les champs qui pourraient contenir nos notes
        for key, value in job_data.items():
            if 'note' in key.lower() or 'tech' in key.lower():
                print(f"🔍 {key}: {repr(value)}")
                
else:
    print(f"❌ Erreur d'authentification: {token_response.status_code} - {token_response.text}")
