# update.ps1 - briefings 폴더를 스캔하여 manifest.json 생성 후 GitHub에 push
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "=== 시황브리핑 자동 업로드 ===" -ForegroundColor Cyan
Write-Host ""

# 1. briefings 폴더 스캔
$files = Get-ChildItem "$root\briefings\*.html" | Where-Object { $_.Name -match '^\d{4}_\d{2}_\d{2}_(morning|afternoon|night)\.html$' }

if ($files.Count -eq 0) {
    Write-Host "[!] briefings/ 폴더에 HTML 파일이 없습니다." -ForegroundColor Yellow
    Read-Host "아무 키나 누르면 종료"
    exit
}

# 2. 파일명 파싱 → 날짜별 그룹핑
$days = @{}
$dayNames = @('일','월','화','수','목','금','토')
$periodMap = @{ 'morning' = @{ period = '오전'; emoji = [char]::ConvertFromUtf32(0x1F305); time = '07:30' }; 'afternoon' = @{ period = '오후'; emoji = [char]::ConvertFromUtf32(0x2600) + [char]::ConvertFromUtf32(0xFE0F); time = '16:00' }; 'night' = @{ period = '밤'; emoji = [char]::ConvertFromUtf32(0x1F319); time = '23:00' } }

foreach ($f in $files) {
    if ($f.Name -match '^(\d{4})_(\d{2})_(\d{2})_(morning|afternoon|night)\.html$') {
        $y = $Matches[1]; $m = $Matches[2]; $d = $Matches[3]; $p = $Matches[4]
        $dateKey = "$y-$m-$d"
        if (-not $days.ContainsKey($dateKey)) {
            $dt = [datetime]::ParseExact("$y-$m-$d", "yyyy-MM-dd", $null)
            $dayName = $dayNames[$dt.DayOfWeek.value__]
            $days[$dateKey] = @{
                date = $dateKey
                label = "${y}년 $([int]$m)월 $([int]$d)일 (${dayName})"
                sessions = @()
            }
        }
        $info = $periodMap[$p]
        $days[$dateKey].sessions += @{
            period = $info.period
            emoji = $info.emoji
            time = $info.time
            file = "briefings/$($f.Name)"
            ready = $true
        }
    }
}

# 3. 세션 정렬 (오전→오후→밤) 및 날짜 정렬
$order = @{ '오전' = 0; '오후' = 1; '밤' = 2 }
$result = $days.Values | Sort-Object { $_.date } | ForEach-Object {
    $_.sessions = $_.sessions | Sort-Object { $order[$_.period] }
    $_
}

# 4. manifest.json 저장
$json = $result | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText("$root\briefings\manifest.json", $json, [System.Text.Encoding]::UTF8)
Write-Host "[OK] manifest.json 생성 완료 ($($files.Count)개 파일 반영)" -ForegroundColor Green

# 5. Git commit & push
Write-Host ""
Write-Host "--- Git 업로드 ---" -ForegroundColor Cyan

git add -A
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "[!] 변경사항 없음. 이미 최신 상태입니다." -ForegroundColor Yellow
} else {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "briefing update: $timestamp"
    git push origin main
    Write-Host ""
    Write-Host "[OK] GitHub 업로드 완료!" -ForegroundColor Green
    Write-Host "     https://jisun5304-kr.github.io/briefing/" -ForegroundColor Gray
}

Write-Host ""
Read-Host "아무 키나 누르면 종료"
