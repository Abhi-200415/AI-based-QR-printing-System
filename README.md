<div align="center">

# 🚀 AI-BASED QR SMART PRINTING SYSTEM

## Cloud-Based Intelligent Printing Platform

### **QR-Based Shop Access • Cloud Printing • AI/ML • Payment Verification • Smart Queue • Local Print Agent • Printer Automation**

<br>

<img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white">
<img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white">
<img src="https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white">
<img src="https://img.shields.io/badge/Neon-Cloud%20Database-00E599?style=for-the-badge">
<img src="https://img.shields.io/badge/AI%2FML-Intelligent%20Printing-8A2BE2?style=for-the-badge">
<img src="https://img.shields.io/badge/Render-Cloud%20Deployment-46E3B7?style=for-the-badge">

<br><br>

**Academic Major Project**

</div>

---

# 📌 1. What Is This Project?

The **AI-Based QR Smart Printing System** is a cloud-based platform that allows customers to submit printing jobs to a printing shop **without standing in the traditional printing queue**.

The main idea is simple:

> **A customer scans the QR code of a printing shop, uploads their document, selects printing requirements, sees the price, completes payment, and submits the print job remotely.**

The submitted job is then handled by the cloud backend.

The backend:

- identifies the correct shop,
- stores the job information,
- calculates the printing cost,
- verifies payment,
- places the job in the queue,
- selects a suitable printer,
- and sends the job toward the printer through a **Local Print Agent**.

The Local Print Agent runs on the computer inside the printing shop and acts as the bridge between the **cloud system and the physical printer**.

So the complete idea is:

```text
CUSTOMER
   ↓
SHOP QR
   ↓
CUSTOMER WEBSITE
   ↓
CLOUD BACKEND
   ↓
PAYMENT + DATABASE + QUEUE + AI
   ↓
LOCAL PRINT AGENT
   ↓
PHYSICAL PRINTER
