# 장면을 다시 짓고 69프레임 렌더 -> MP4
$ErrorActionPreference = "Continue"
$blender = "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
$d = "C:\Users\tmd39\Documents\별이떨어지는마을\blender"
& $blender --background --factory-startup --python "$d\build_scene.py" -- "$d\scene_export.txt" "$d\town_test.blend" 2>&1 | Select-String -Pattern '^(SAVED|Traceback)|Error:'
if (Test-Path "$d\frames") { Remove-Item "$d\frames\*.png" -ErrorAction SilentlyContinue }
$t = Get-Date
& $blender --background "$d\town_test.blend" -a 2>&1 | Select-String -Pattern 'Saved:|Traceback' | ForEach-Object { $_.Line }
"render {0:N0}s" -f ((Get-Date) - $t).TotalSeconds
ffmpeg -v error -y -framerate 30 -start_number 1 -i "$d\frames\f%04d.png" -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p "$d\blender_test_shot03_04.mp4"
"mp4 done"
