# Security Checklist & Threat Model

This document outlines the security architecture, OWASP mitigations, data classification, encryption workflows, and audit logging standards for Amrutam's Telemedicine System.

---

## 1. Data Classification

Data within the system is categorized to enforce appropriate security and storage constraints:

| Category | Description | Fields / Tables | Encryption Standards | Storage Location |
| :--- | :--- | :--- | :--- | :--- |
| **Protected Health Information (PHI)** | Medical records, diagnostics, prescriptions, consultation notes. | `prescriptions.diagnosis`, `prescriptions.medications` | Application-Level AES-256-GCM + KMS KMS-envelope key | PostgreSQL |
| **Personally Identifiable Information (PII)** | Patient profile details, contact information, identity fields. | `profiles.first_name`, `profiles.last_name`, `profiles.phone` | Application-Level AES-256-GCM | PostgreSQL |
| **Financial / Billing Data** | Transaction records, pricing, invoice statements. | `payments` table | RDS Database Encryption (AES-256 at Rest) | PostgreSQL |
| **Administrative / Configuration** | System logs, doctor schedules, doctor bios. | `availability_slots`, `doctors` table | RDS Database Encryption (AES-256 at Rest) | PostgreSQL |

---

## 2. Cryptographic Management

### 1. Application-Level Field Encryption (AES-256-GCM)
- Sensitive PII/PHI columns are encrypted inside application memory before hitting the database driver (Postgres adapter).
- **Algorithm**: AES-256-GCM.
- **Envelope Encryption Workflow**:
  - The application uses a master key from environment variables (or AWS KMS) to encrypt columns.
  - A unique cryptographically secure random 12-byte initialization vector (nonce) is generated for each write operation.
  - Nonce is concatenated to the ciphertext output: `Base64(nonce + ciphertext)`.
  - Upon query retrieval, the base64 payload is parsed, the 12-byte nonce extracted, and the string decrypted.

### 2. Digital Signatures for Prescriptions
- Every prescription includes a digital signature.
- **Workflow**:
  - The doctor signs the payload `(consultation_id + diagnosis + medications_json)` using their private key.
  - The signature is stored in `prescriptions.doctor_signature`.
  - Pharmacies or patients can verify the signature using the doctor's public key, preventing tampering.

### 3. Key Rotation Policy
- **Automatic Rotation**: Application encryption keys must be rotated every 12 months.
- **Migration Logic**:
  - When keys are rotated, a new key ID is added.
  - The decryption algorithm tries the active key; if it fails, it falls back to older key IDs in the rotation chain.
  - When a record is updated, it is re-encrypted using the new active key.

---

## 3. OWASP Top 10 Mitigation Matrix

| Vulnerability Category | Risk Scenario | Mitigation Strategy |
| :--- | :--- | :--- |
| **A01:2021-Broken Access Control** | Patient viewing another patient's prescription or booking. | Enforce rigid tenancy verification dependencies checking user ownership (e.g. `patient_id == current_user.id`) in service/repository layer. Route decorators validate OAuth2 token scopes. |
| **A02:2021-Cryptographic Failures** | Data leak due to database copy exposure. | Force AES-256-GCM encryption on health/profile fields. Implement TLS 1.3 in transit and enable AWS RDS KMS encryption at rest. |
| **A03:2021-Injection** | SQL Injection exposing client tables. | Utilize SQLAlchemy 2.0 object-relational mapping which uses prepared parameters automatically. Input validation is strictly enforced via Pydantic. |
| **A04:2021-Insecure Design** | Double-booking of doctors, race conditions. | Implement pessimistic locking (`SELECT FOR UPDATE`) inside transactions combined with database unique constraints. |
| **A05:2021-Security Misconfiguration** | Exposure of debug endpoints or environment vars. | Disable FastAPI interactive documentation `/docs` in production environment. Load variables through secure secret vaults (AWS Secrets Manager). |
| **A06:2021-Vulnerable and Outdated Components** | Dependencies with CVEs. | Incorporate automatic vulnerability scanning (`safety` or `snyk`) in the CI pipeline. Use specific versions in `requirements.txt`. |
| **A07:2021-Identification and Authentication Failures** | Brute force login, stolen credentials. | Force Multi-Factor Authentication (TOTP via `pyotp`). Hash passwords using bcrypt. Implement token expiration times (15-30 minutes). |
| **A08:2021-Software and Data Integrity Failures** | Prescription data altered directly in database. | Enforce doctor digital cryptographic signature checks on prescriptions to guarantee integrity. |
| **A09:2021-Security Logging and Monitoring Failures** | Unauthorized PHI accesses are unrecorded. | Structured JSON logs contain correlation IDs. Create immutable logs in `audit_logs` tracking every read/write to sensitive tables. |
| **A10:2021-Server-Side Request Forgery** | Application makes malicious outward requests. | Sandbox outward calls using configured proxy layers and block server access to local metadata endpoints (e.g. EC2 `169.254.169.254`). |

---

## 4. Threat Model (STRIDE Framework)

We analyze system vulnerabilities using STRIDE:

- **Spoofing**: Attackers pretending to be a doctor.
  - *Mitigation*: Enable MFA (TOTP) during login. JWT signatures verify identity.
- **Tampering**: Modifying prescription fields directly in database.
  - *Mitigation*: Application checks doctor's cryptographic signature. If text hash doesn't match signature, the app flags the record as corrupted.
- **Repudiation**: Doctor claiming they did not issue a prescription.
  - *Mitigation*: Doctor signatures verify origin. Non-repudiation is achieved since only the owner of the private key could sign the payload.
- **Information Disclosure**: Unauthorized access to medical records.
  - *Mitigation*: Columns are encrypted with AES-256-GCM. Unencrypted database files are unreadable.
- **Denial of Service**: Overloading API resources.
  - *Mitigation*: Rate limit requests using Redis-backed token bucket middleware. Scale containers horizontally via ALB metrics.
- **Elevation of Privilege**: Patient accessing admin analytics.
  - *Mitigation*: Role-based Access Control (RBAC) checked at route level using FastAPI dependency injection.

---

## 5. Security & Compliance Audit Trail
The system writes to the `audit_logs` table for compliance audits:
1. **Immutable Records**: Logs cannot be modified. The DB role assigned to the application has only `INSERT` permission on `audit_logs` (preventing `UPDATE` or `DELETE`).
2. **Payload Integrity**: Every audit log stores a SHA-256 hash of the request context and parameters (`payload_hash`).
3. **Trigger Scenarios**:
   - `register_user`, `login_attempt`, `login_mfa_success`, `enable_mfa`.
   - `create_slot`, `book_consultation`, `view_consultation`, `add_prescription`.
   - `process_payment`.
