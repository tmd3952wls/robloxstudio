# 렌더 프레임(frames_r4) + 믹스(mix.wav) + 한 단어 자막(subs.ass) -> 최종 mp4
param([int]$Frames = 0)
$root = "C:\Users\tmd39\Documents\별이떨어지는마을"
$fr = "$root\blender\frames_r5"
$a = "$root\audio"
Push-Location $a
$limit = @()
if ($Frames -gt 0) { $limit = @("-frames:v", "$Frames") }
ffmpeg -y -v error -framerate 30 -start_number 1 -i "$fr\f%04d.png" -i "mix.wav" @limit -vf "subtitles=subs.ass:fontsdir=fonts" -c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p -c:a aac -b:a 256k -shortest -movflags +faststart "$root\별이떨어지는마을_최종.mp4"
Pop-Location
ffprobe -v error -show_entries format=duration -of csv=p=0 "$root\별이떨어지는마을_최종.mp4"
