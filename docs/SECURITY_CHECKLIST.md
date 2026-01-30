# Security Checklist

Pre-deployment security review checklist for Framework Ottotor.

## Pre-Deployment Checklist

### Infrastructure Security

- [ ] **Container Security**
  - [ ] Running as non-root user (UID 1000)
  - [ ] Read-only root filesystem where possible
  - [ ] No privileged containers
  - [ ] Resource limits set (CPU, memory)
  - [ ] Security context configured (drop ALL capabilities)

- [ ] **Network Security**
  - [ ] API not exposed to public internet without authentication
  - [ ] Network policies restrict pod-to-pod communication
  - [ ] TLS 1.2+ for all external communications
  - [ ] Egress rules limit outbound connections

- [ ] **Secrets Management**
  - [ ] No secrets in environment variables visible in logs
  - [ ] Secrets stored in Kubernetes Secrets or external vault
  - [ ] Secrets rotated on regular schedule
  - [ ] No secrets in container images or ConfigMaps

### Application Security

- [ ] **Input Validation**
  - [ ] All task inputs validated (`validation.py`)
  - [ ] Path traversal prevention verified
  - [ ] JSON schema validation for domain configs
  - [ ] Input size limits enforced

- [ ] **Output Sanitization**
  - [ ] Sensitive data redacted from logs
  - [ ] Error messages don't leak internal details
  - [ ] Correlation IDs don't contain sensitive data

- [ ] **Authentication & Authorization**
  - [ ] API gateway or service mesh provides auth
  - [ ] Rate limiting prevents abuse
  - [ ] No default credentials

### Dependency Security

- [ ] **Dependency Management**
  - [ ] Dependabot enabled for automated updates
  - [ ] `pip-audit` shows no critical vulnerabilities
  - [ ] `safety check` passes
  - [ ] Bandit security linting passes

- [ ] **Base Image**
  - [ ] Using official Python slim image
  - [ ] Image scanned for vulnerabilities (Trivy/Snyk)
  - [ ] No unnecessary packages installed

### Operational Security

- [ ] **Logging & Monitoring**
  - [ ] Security events logged (rate limits, circuit breaks)
  - [ ] Log aggregation configured
  - [ ] Alerting rules deployed
  - [ ] No sensitive data in logs

- [ ] **Incident Response**
  - [ ] Runbooks available for common issues
  - [ ] Circuit breaker alerts configured
  - [ ] Health check monitoring active
  - [ ] Rollback procedure documented

### Compliance

- [ ] **Data Protection**
  - [ ] Checkpoint data encrypted at rest (if sensitive)
  - [ ] Data retention policies defined
  - [ ] PII handling documented

- [ ] **Audit Trail**
  - [ ] Correlation IDs enable request tracing
  - [ ] Agent execution logged
  - [ ] Configuration changes tracked

---

## Security Testing Commands

### Run Security Linting

```bash
# Bandit - Python security linter
pip install bandit
bandit -r . -x ./tests -f txt

# Safety - Dependency vulnerability check
pip install safety
safety check

# pip-audit - Dependency audit
pip install pip-audit
pip-audit --strict
```

### Container Scanning

```bash
# Trivy - Container vulnerability scanner
trivy image framework-ottotor:latest

# Snyk - Container and dependency scan
snyk container test framework-ottotor:latest
```

### OWASP Dependency Check

```bash
# For comprehensive dependency analysis
dependency-check --project framework-ottotor --scan .
```

---

## Security Configuration Reference

### Recommended Kubernetes SecurityContext

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true
```

### Recommended Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: framework-ottotor-policy
spec:
  podSelector:
    matchLabels:
      app: framework-ottotor
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: prometheus
      ports:
        - port: 9090
```

### Environment Variable Security

```bash
# DO NOT do this
export API_KEY="secret123"  # Visible in process list

# DO this instead
# Use Kubernetes secrets mounted as files
# Or use external secrets management (Vault, AWS Secrets Manager)
```

---

## Vulnerability Response Process

1. **Triage** - Assess severity using CVSS score
2. **Notify** - Alert stakeholders for Critical/High severity
3. **Patch** - Apply fix or mitigation
4. **Verify** - Confirm fix with security testing
5. **Document** - Update CHANGELOG and notify users

### Severity Response Times

| Severity | Response Time | Resolution Time |
|----------|---------------|-----------------|
| Critical | 4 hours | 24 hours |
| High | 24 hours | 7 days |
| Medium | 7 days | 30 days |
| Low | 30 days | Next release |

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
- [NIST Container Security Guide](https://csrc.nist.gov/publications/detail/sp/800-190/final)
- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)

---

*Last updated: 2026-01-23*
