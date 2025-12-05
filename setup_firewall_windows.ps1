# Script PowerShell pour autoriser les ports de Screen Sharing sur Windows
# Exécutez ce script en tant qu'ADMINISTRATEUR sur PC-3 (Windows serveur)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CONFIGURATION PARE-FEU WINDOWS" -ForegroundColor Cyan
Write-Host "  Screen Sharing Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Port TCP pour les commandes (obligatoire)
$tcpPort = 9998
Write-Host "🔧 Autorisation du port TCP $tcpPort (commandes)..." -ForegroundColor Yellow

try {
    # Supprimer règle existante si présente
    Remove-NetFirewallRule -DisplayName "ScreenShare TCP $tcpPort" -ErrorAction SilentlyContinue
    
    # Créer nouvelle règle
    New-NetFirewallRule -DisplayName "ScreenShare TCP $tcpPort" `
                        -Direction Inbound `
                        -Protocol TCP `
                        -LocalPort $tcpPort `
                        -Action Allow `
                        -Profile Any | Out-Null
    
    Write-Host "✅ Port TCP $tcpPort autorisé" -ForegroundColor Green
} catch {
    Write-Host "❌ Erreur: $_" -ForegroundColor Red
}

Write-Host ""

# Port UDP pour la vidéo (recommandé)
$udpPort = 9999
Write-Host "🔧 Autorisation du port UDP $udpPort (vidéo)..." -ForegroundColor Yellow

try {
    # Supprimer règle existante si présente
    Remove-NetFirewallRule -DisplayName "ScreenShare UDP $udpPort" -ErrorAction SilentlyContinue
    
    # Créer nouvelle règle
    New-NetFirewallRule -DisplayName "ScreenShare UDP $udpPort" `
                        -Direction Inbound `
                        -Protocol UDP `
                        -LocalPort $udpPort `
                        -Action Allow `
                        -Profile Any | Out-Null
    
    Write-Host "✅ Port UDP $udpPort autorisé" -ForegroundColor Green
} catch {
    Write-Host "❌ Erreur: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✨ Configuration terminée!" -ForegroundColor Green
Write-Host ""
Write-Host "🔍 Vérification des règles créées:" -ForegroundColor Cyan
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "ScreenShare*"} | Format-Table DisplayName, Enabled, Direction, Action

Write-Host ""
Write-Host "📝 Pour tester la connexion depuis PC-1:" -ForegroundColor Yellow
Write-Host "   python test_connection.py 192.168.11.19" -ForegroundColor White
Write-Host ""
