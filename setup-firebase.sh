#!/bin/bash

# Firebase setup script for Jamie frontend deployment
set -e

# Get project ID from environment variable
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}

echo "Setting up Firebase for Jamie frontend deployment..."
echo "Using project ID: ${PROJECT_ID}"

# Check if Firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo "Installing Firebase CLI..."
    # Try with sudo first, fallback to user install
    if ! sudo npm install -g firebase-tools 2>/dev/null; then
        echo "Global install failed, trying user install..."
        npm install firebase-tools
        echo "Please add $(npm config get prefix)/bin to your PATH"
        echo "Or run: export PATH=\$(npm config get prefix)/bin:\$PATH"
    fi
fi

# Login to Firebase
echo "Please login to Firebase..."
firebase login

# Initialize Firebase hosting
echo "Initializing Firebase hosting..."
firebase init hosting --project ${PROJECT_ID}

echo ""
echo "Firebase setup complete!"
echo "You can now run the deploy script to deploy your frontend to Firebase Hosting."
