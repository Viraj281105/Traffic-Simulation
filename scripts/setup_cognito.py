import boto3
import json
import os
import sys

def setup_cognito(pool_name="TrafficSimulationUserPool"):
    print(f"Setting up Cognito User Pool: {pool_name}...")
    
    # Initialize the Cognito Identity Provider client
    try:
        client = boto3.client('cognito-idp')
    except Exception as e:
        print("Error initializing boto3 client. Please ensure you have AWS credentials configured (e.g., via 'aws configure').")
        print(e)
        sys.exit(1)
        
    try:
        # Create User Pool
        response = client.create_user_pool(
            PoolName=pool_name,
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8,
                    'RequireUppercase': True,
                    'RequireLowercase': True,
                    'RequireNumbers': True,
                    'RequireSymbols': False
                }
            },
            AutoVerifiedAttributes=['email'],
            UsernameAttributes=['email'],
            Schema=[
                {
                    'Name': 'email',
                    'AttributeDataType': 'String',
                    'DeveloperOnlyAttribute': False,
                    'Mutable': True,
                    'Required': True
                }
            ]
        )
        
        user_pool_id = response['UserPool']['Id']
        print(f"User Pool created successfully. ID: {user_pool_id}")
        
        # Create User Pool Client
        client_name = f"{pool_name}Client"
        client_response = client.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName=client_name,
            GenerateSecret=False, # Web apps generally don't use client secrets
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH',
                'ALLOW_USER_SRP_AUTH'
            ]
        )
        
        client_id = client_response['UserPoolClient']['ClientId']
        print(f"User Pool Client created successfully. Client ID: {client_id}")
        
        # Get region
        region = client.meta.region_name
        
        # Output configuration
        print("\n=== SETUP COMPLETE ===")
        print("Please add the following to your frontend/.env file:")
        print(f"VITE_COGNITO_REGION={region}")
        print(f"VITE_COGNITO_USER_POOL_ID={user_pool_id}")
        print(f"VITE_COGNITO_CLIENT_ID={client_id}")
        print("\nAnd add the following to your backend/.env file:")
        print(f"AWS_REGION={region}")
        print(f"COGNITO_USER_POOL_ID={user_pool_id}")
        print(f"COGNITO_CLIENT_ID={client_id}")
        
        # Write to .env files automatically if they exist
        update_env_file('../frontend/.env', {
            'VITE_COGNITO_REGION': region,
            'VITE_COGNITO_USER_POOL_ID': user_pool_id,
            'VITE_COGNITO_CLIENT_ID': client_id
        })
        
        update_env_file('../backend/.env', {
            'AWS_REGION': region,
            'COGNITO_USER_POOL_ID': user_pool_id,
            'COGNITO_CLIENT_ID': client_id
        })

    except Exception as e:
        print(f"An error occurred: {e}")

def update_env_file(filepath, updates):
    path = os.path.join(os.path.dirname(__file__), filepath)
    env_vars = {}
    
    # Read existing
    if os.path.exists(path):
        with open(path, 'r') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    env_vars[k] = v
                    
    # Update
    env_vars.update(updates)
    
    # Write back
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")
    print(f"Updated {os.path.abspath(path)}")

if __name__ == "__main__":
    setup_cognito()
