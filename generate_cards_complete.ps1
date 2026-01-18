# CSV에서 Vue contentItems로 변환하는 스크립트
$csv = Import-Csv '.\src\assets\extracted_data copy.csv' -Encoding UTF8

$iconMap = @{
  510='🤖'; 511='🔍'; 512='🎨'; 513='🔗'; 514='⚡'; 515='🗄️'; 516='🛡️'; 517='☸️'; 518='🔄'; 519='🚪'; 520='🔄'
  530='💿'; 531='📈'; 532='🌊'; 533='📊'; 534='🔗'; 535='🤝'
  540='🔒'; 541='🛡️'; 542='🔐'; 543='🔍'; 544='👥'; 545='📋'; 546='🏰'; 547='⚠️'; 548='🚫'; 549='🔑'
  550='☁️'; 551='🛡️'
  560='🤖'; 562='🎯'; 564='🎯'; 565='⚙️'; 568='💬'
  570='🏗️'; 571='🍕'; 572='🔧'
  580='💻'; 581='👥'; 582='🖥️'; 583='🤖'; 584='🧠'; 585='⚡'; 587='🔎'
  590='💬'
  595='🏥'; 596='🏥'; 597='🌍'; 598='💊'
  500='🔭'; 502='🔧'; 503='☁️'; 504='🌐'; 505='🐧'; 506='🪟'
  13='📊'; 14='📦'; 15='📦'; 16='💾'; 17='📋'; 18='🔒'; 19='👨‍💼'; 20='📋'
}

$output = "const contentItems = [`n"
$id = 1

foreach ($row in $csv) {
  $title = $row.Title_kr -replace '"', '\"' -replace "'", "'"
  $desc = $row.Session_Description_kr -replace '"', '\"' -replace "'", "'" -replace "`r`n", ' ' -replace "`n", ' '
  
  if ($desc.Length -gt 200) {
    $desc = $desc.Substring(0, 200)
  }
  
  # Icon 결정
  $icon = '📄'
  if ($title -match 'LAB(\d+)') {
    $num = [int]$Matches[1]
    if ($iconMap.ContainsKey($num)) {
      $icon = $iconMap[$num]
    }
  } elseif ($title -match 'PREL(\d+)') {
    $num = [int]$Matches[1]
    if ($iconMap.ContainsKey($num)) {
      $icon = $iconMap[$num]
    }
  }
  
  # 태그 생성
  $cats = $row.Categories -split ';'
  $tagLines = @()
  foreach ($cat in $cats) {
    $catTrim = $cat.Trim()
    if ($catTrim) {
      $color = 'workshop'
      if ($catTrim -in @('Azure','Security','Governance')) { 
        $color = 'azure' 
      } elseif ($catTrim -in @('Data','Analytics','DevOps','Kubernetes','Migration')) { 
        $color = 'tutorial' 
      } elseif ($catTrim -in @('Healthcare','Microsoft 365')) { 
        $color = 'm365' 
      }
      $tagLines += "      { label: '$catTrim', color: '$color' }"
    }
  }
  $tagsStr = $tagLines -join ",`n"
  
  # 카드 객체 생성
  $output += "  {`n"
  $output += "    id: $id,`n"
  $output += "    icon: '$icon',`n"
  $output += "    title: '$title',`n"
  $output += "    description: '$desc',`n"
  $output += "    tags: [`n$tagsStr`n    ],`n"
  $output += "    actions: [`n"
  $output += "      { label: 'PDF', icon: 'pdf', primary: false },`n"
  $output += "      { label: 'YouTube', icon: 'youtube', primary: false },`n"
  $output += "      { label: 'GitHub', icon: 'github', primary: true }`n"
  $output += "    ]`n"
  $output += "  }"
  
  if ($id -lt $csv.Count) {
    $output += ","
  }
  $output += "`n"
  $id++
}

$output += "]"

# UTF-8 BOM 없이 저장
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$PSScriptRoot\contentItems.js", $output, $utf8NoBom)

Write-Host "✅ Generated $($id-1) cards successfully!" -ForegroundColor Green
Write-Host "📁 Output saved to: contentItems.js" -ForegroundColor Cyan
