$csv = Import-Csv "c:\Work\Azure\buildflow\src\assets\extracted_data copy.csv"
Write-Host "총 $($csv.Count)개 레코드 처리 시작..."

$result = "const contentItems = [`n"
$id = 1

foreach ($row in $csv) {
    # Categories 처리
    $categories = $row.Categories -split ';' | Where-Object { $_.Trim() -ne '' }
    $tags = @()
    
    foreach ($cat in $categories) {
        $catTrim = $cat.Trim()
        $color = 'azure'
        
        if ($catTrim -in @('AI', 'Agent', 'Copilot')) { $color = 'workshop' }
        elseif ($catTrim -in @('Data', 'Analytics', 'DevOps', 'Kubernetes', 'Migration', 'Machine Learning')) { $color = 'tutorial' }
        elseif ($catTrim -in @('Healthcare', 'Microsoft 365')) { $color = 'm365' }
        elseif ($catTrim -in @('Azure', 'Security', 'Governance', 'Compliance', 'Sustainability', 'Hybrid', 'Monitoring')) { $color = 'azure' }
        
        $tags += "      { label: '$catTrim', color: '$color' }"
    }
    
    # 아이콘 선택
    $icon = '🎯'
    if ($row.Title_kr -match '510') { $icon = '🤖' }
    elseif ($row.Title_kr -match '511') { $icon = '🔍' }
    elseif ($row.Title_kr -match '512') { $icon = '🎨' }
    elseif ($row.Title_kr -match '513') { $icon = '🔗' }
    elseif ($row.Title_kr -match '514') { $icon = '⚡' }
    elseif ($row.Title_kr -match '515') { $icon = '🗄️' }
    elseif ($row.Title_kr -match '516') { $icon = '🛡️' }
    elseif ($row.Title_kr -match '517') { $icon = '☸️' }
    elseif ($row.Title_kr -match '518') { $icon = '🔄' }
    elseif ($row.Title_kr -match '519') { $icon = '🚪' }
    elseif ($row.Title_kr -match '571') { $icon = '🍕' }
    elseif ($row.Title_kr -match '596') { $icon = '🏥' }
    elseif ($row.Title_kr -match '598') { $icon = '💊' }
    elseif ($row.Title_kr -match 'PREL13') { $icon = '📊' }
    elseif ($row.Title_kr -match 'PREL15') { $icon = '📦' }
    elseif ($row.Title_kr -match 'PREL16') { $icon = '💾' }
    elseif ($row.Title_kr -match 'PREL19') { $icon = '👨‍💼' }
    elseif ($row.Title_kr -match '500') { $icon = '🔭' }
    elseif ($row.Title_kr -match '502') { $icon = '🔧' }
    elseif ($row.Title_kr -match '503') { $icon = '☁️' }
    elseif ($row.Title_kr -match '504') { $icon = '🌐' }
    elseif ($row.Title_kr -match '505') { $icon = '🐧' }
    elseif ($row.Title_kr -match '506') { $icon = '🪟' }
    elseif ($row.Title_kr -match '520') { $icon = '🔄' }
    elseif ($row.Title_kr -match '597') { $icon = '🌍' }
    elseif ($row.Title_kr -match 'PREL20') { $icon = '📋' }
    elseif ($row.Title_kr -match '530') { $icon = '💿' }
    elseif ($row.Title_kr -match '531') { $icon = '📈' }
    
    # 텍스트 처리
    $title = $row.Title_kr -replace "'", "\\'" -replace '"', '\\"'
    $desc = $row.Session_Description_kr
    if ($desc.Length -gt 200) { $desc = $desc.Substring(0, 200) }
    $desc = $desc -replace "'", "\\'" -replace '"', '\\"' -replace "`n", " " -replace "`r", ""
    
    if ($id -gt 1) { $result += ",`n" }
    
    $result += "  {`n"
    $result += "    id: $id,`n"
    $result += "    icon: '$icon',`n"
    $result += "    title: '$title',`n"
    $result += "    description: '$desc',`n"
    $result += "    tags: [`n"
    $result += ($tags -join ",`n")
    $result += "`n    ],`n"
    $result += "    actions: [`n"
    $result += "      { label: 'PDF', icon: 'pdf', primary: false },`n"
    $result += "      { label: 'YouTube', icon: 'youtube', primary: false },`n"
    $result += "      { label: 'GitHub', icon: 'github', primary: true }`n"
    $result += "    ]`n"
    $result += "  }"
    
    $id++
}

$result += "`n]"
$result | Out-File "c:\Work\Azure\buildflow\contentItems_output.txt" -Encoding UTF8
Write-Host "완료! 총 $($id - 1)개 카드가 생성되었습니다."
Write-Host "결과 파일: c:\Work\Azure\buildflow\contentItems_output.txt"
