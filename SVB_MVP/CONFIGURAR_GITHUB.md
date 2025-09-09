# ⚠️ ATENÇÃO: Configuração do GitHub Necessária

## Seu repositório Git local está pronto, mas precisa conectar ao GitHub!

### 📋 PASSOS OBRIGATÓRIOS:

#### 1. Criar repositório no GitHub
- Acesse: https://github.com
- Clique em "New repository" (botão verde)
- Nome: `SVB_MVP`
- Tipo: **Público** (para usar Streamlit Cloud gratuito)
- **NÃO** marque "Initialize with README"
- Clique "Create repository"

#### 2. Conectar seu projeto ao GitHub
Copie e execute no PowerShell (substitua SEU-USUARIO pelo seu nome de usuário do GitHub):

```powershell
cd "c:\Users\Bruno\Downloads\SVB_MVP"
git remote add origin https://github.com/SEU-USUARIO/SVB_MVP.git
git push -u origin main
```

#### 3. Testar o script de atualização
Após configurar o GitHub, teste:
```powershell
.\atualizar.bat
```

### 🔍 Como descobrir seu nome de usuário GitHub:
- Entre no GitHub
- Clique na sua foto (canto superior direito)
- Seu nome aparece no menu (exemplo: @brunodeveloper)
- Use apenas a parte após o @ (exemplo: brunodeveloper)

### 📱 Exemplo completo:
Se seu usuário for "brunodeveloper":
```powershell
git remote add origin https://github.com/brunodeveloper/SVB_MVP.git
git push -u origin main
```

### ✅ Depois da configuração:
1. ✅ `atualizar.bat` funcionará perfeitamente
2. ✅ Streamlit Cloud detectará mudanças automaticamente
3. ✅ Equipe verá atualizações em tempo real
