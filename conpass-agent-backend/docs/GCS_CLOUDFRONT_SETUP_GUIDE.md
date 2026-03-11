# Google Cloud Storage & Cloud CDN Setup Guide

This guide outlines the steps to configure Google Cloud Storage (GCS) and Google Cloud CDN for the file upload system.

## 1. Google Cloud Storage (GCS) Setup

### Step 1: Create a Bucket
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Navigate to **Cloud Storage** > **Buckets**.
3.  Click **CREATE**.
4.  **Name your bucket**: Choose a globally unique name (e.g., `conpass-uploads-prod`).
5.  **Location type**: Choose `Region` (e.g., `asia-northeast1` for Tokyo) or `Multi-region` depending on your latency requirements.
6.  **Storage Class**: `Standard` is recommended for frequently accessed files.
7.  **Access Control**: Choose `Uniform` for simpler permission management.
8.  **Protection**: Uncheck "Enforce public access prevention on this bucket" if you plan to make objects public directly or keep it checked if using a Load Balancer/CDN with a backend service.
    *   *Recommendation*: Keep it private and grant access to a specific Service Account used by the API.

### Step 2: Configure Permissions (Existing Service Account)
1.  **Identify your existing Service Account**: Locate the service account email currently used for other cloud communications (likely in `IAM & Admin` > `Service Accounts`).
2.  **Grant Permissions**:
    *   Find the existing Service Account in the IAM list.
    *   Click "Edit Principal" (pencil icon) or "Grant Access".
    *   Add the following roles to this Service Account for the **specific bucket** (or at project level if acceptable):
        *   `Storage Object Creator`: To upload files.
        *   `Storage Object Viewer`: To read files.
3.  **Authentication**: Ensure your application is already using the credentials for this account (via `GOOGLE_APPLICATION_CREDENTIALS` or environment-native auth). **No new key generation is needed** if already configured.

## 2. Cloud CDN Configuration

1.  **Create a Load Balancer**: Go to **Network Services** > **Load balancing**.
2.  Start configuration for an **HTTP(S) Load Balancer**.
3.  **Backend Configuration**:
    *   Create a backend bucket.
    *   Select the GCS bucket you created in Step 1.
    *   Check **Enable Cloud CDN**.
4.  **Frontend Configuration**:
    *   Reserve a static IP address.
    *   Configure your SSL certificate (Google-managed or self-managed).
5.  **DNS & Domain**:
    *   **Where do I get this?**: This is a custom domain you own (e.g., if you own `example.com`, you can create `cdn.example.com`).
    *   **Action**: Go to your DNS provider (Godaddy, Google Domains, Route53, etc.) and create an **A Record** for your chosen subdomain (e.g., `cdn`) pointing to the **Static IP Address** reserved in the previous step.
    *   **Note**: If you do not have a custom domain, you can use the raw IP address (e.g., `34.x.x.x`), but SSL/HTTPS functionality will incur warnings or fail. A custom domain with a Google-managed certificate is recommended.

## 3. Configuration in Application

Update your `.env` or `app/core/config.py`:

```bash
GCS_BUCKET_NAME="your-bucket-name"
# Cloud CDN Domain
CDN_DOMAIN="cdn.yourdomain.com"
```
