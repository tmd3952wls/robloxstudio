# 같은 타임코드의 기존 수정본(frames_r2, 없으면 frames_full) → 이번 수정본(frames_r3p)을 이어 붙인 비교 영상.
# 화면 왼쪽 위 "기존 / 이번" 표시는 비교용이며 본편에는 들어가지 않는다.
param([string]$NewDir = "frames_r3p", [string]$OutName = "비교_r3")
$d = "C:\Users\tmd39\Documents\별이떨어지는마을\blender"
$out = Join-Path $d $OutName
New-Item -ItemType Directory -Force $out | Out-Null
$seg = Join-Path $out "_seg"
New-Item -ItemType Directory -Force $seg | Out-Null
$prev = Join-Path $out "_prev"
New-Item -ItemType Directory -Force $prev | Out-Null
$font = "C\:/Windows/Fonts/malgunbd.ttf"

function Link-Prev($a, $b) {
    for ($f = $a; $f -le $b; $f++) {
        $n = "f{0:D4}.png" -f $f
        $dst = Join-Path $prev $n
        if (Test-Path $dst) { continue }
        $src = Join-Path "$d\frames_r2" $n
        if (-not (Test-Path $src)) { $src = Join-Path "$d\frames_full" $n }
        New-Item -ItemType HardLink -Path $dst -Target $src | Out-Null
    }
}
function Make-Seg($src, $a, $b, $label, $name) {
    $n = $b - $a + 1
    $tf = "$seg\$name.label.txt"
    [IO.File]::WriteAllText($tf, $label, (New-Object Text.UTF8Encoding($false)))
    $tfe = ($tf -replace '\\', '/') -replace ':', '\:'
    $txt = "drawtext=fontfile='$font':textfile='$tfe':x=40:y=60:fontsize=46:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=14"
    ffmpeg -y -v error -framerate 30 -start_number $a -i "$src\f%04d.png" -frames:v $n -vf $txt -c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p "$seg\$name.mp4"
}
function TC($f) { $s = ($f - 1) / 30.0; return ("{0}:{1:00.0}" -f [math]::Floor($s / 60), ($s % 60)) }

$groups = @(
    @{ name = "1_오프닝_한번의_비행"; parts = @(,@(1, 129)) },
    @{ name = "2_병을_귀에_대는_장면"; parts = @(,@(1249, 1455)) },
    @{ name = "3_별의_강과_하늘이_켜짐"; parts = @(,@(2170, 2388)) }
)
$all = @()
foreach ($g in $groups) {
    $list = @()
    $i = 0
    foreach ($p in $g.parts) {
        $a, $b = $p[0], $p[1]
        Link-Prev $a $b
        $span = "$(TC $a)~$(TC ($b + 1))"
        Make-Seg $prev $a $b "기존 $span" "$($g.name)_${i}_old"
        Make-Seg "$d\$NewDir" $a $b "이번 수정 $span" "$($g.name)_${i}_new"
        $list += "file '$seg\$($g.name)_${i}_old.mp4'"
        $list += "file '$seg\$($g.name)_${i}_new.mp4'"
        $i++
    }
    $lf = "$seg\$($g.name).txt"
    [IO.File]::WriteAllLines($lf, [string[]]$list, (New-Object Text.UTF8Encoding($false)))
    ffmpeg -y -v error -f concat -safe 0 -i $lf -c copy "$out\비교_$($g.name).mp4"
    $all += $list
}
[IO.File]::WriteAllLines("$seg\all.txt", [string[]]$all, (New-Object Text.UTF8Encoding($false)))
ffmpeg -y -v error -f concat -safe 0 -i "$seg\all.txt" -c copy "$out\비교_전체_세구간.mp4"
Get-ChildItem $out -Filter *.mp4 | ForEach-Object { "{0}  {1:N1}s" -f $_.Name, [double](ffprobe -v error -show_entries format=duration -of csv=p=0 $_.FullName) }
