# 같은 타임코드의 기존본(frames_full) → 수정본(frames_r2)을 이어 붙인 비교 영상을 만든다.
# 화면 왼쪽 위의 "기존 / 수정" 표시는 비교용이며 본편에는 들어가지 않는다.
$d = "C:\Users\tmd39\Documents\별이떨어지는마을\blender"
$out = Join-Path $d "비교"
New-Item -ItemType Directory -Force $out | Out-Null
$seg = Join-Path $out "_seg"
New-Item -ItemType Directory -Force $seg | Out-Null
$font = "C\:/Windows/Fonts/malgunbd.ttf"

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
    @{ name = "1_오프닝"; parts = @(,@(1, 129)) },
    @{ name = "2_손과_어깨의_별"; parts = @(@(187, 267), @(2494, 2568)) },
    @{ name = "3_반응과_달리기"; parts = @(@(1276, 1332), @(1795, 1827)) },
    @{ name = "4_하늘이_다시_켜짐"; parts = @(,@(2281, 2388)) }
)
$all = @()
foreach ($g in $groups) {
    $list = @()
    $i = 0
    foreach ($p in $g.parts) {
        $a, $b = $p[0], $p[1]
        $span = "$(TC $a)~$(TC ($b + 1))"
        Make-Seg "$d\frames_full" $a $b "기존 $span" "$($g.name)_${i}_old"
        Make-Seg "$d\frames_r2" $a $b "수정 $span" "$($g.name)_${i}_new"
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
ffmpeg -y -v error -f concat -safe 0 -i "$seg\all.txt" -c copy "$out\비교_전체_네구간.mp4"
Get-ChildItem $out -Filter *.mp4 | ForEach-Object { "{0}  {1:N1}s" -f $_.Name, [double](ffprobe -v error -show_entries format=duration -of csv=p=0 $_.FullName) }
