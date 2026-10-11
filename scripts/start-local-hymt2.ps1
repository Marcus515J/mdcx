param(
    [string[]]$SearchRoot = @(),
    [string]$LlamaServerPath = "",
    [string]$ModelPath = "",
    [string]$LogRoot = "",
    [ValidateRange(1, 65535)][int]$Port = 8080,
    [ValidateRange(1, 1800)][int]$StartupTimeoutSeconds = 180,
    [switch]$NonInteractive,
    [switch]$FromLauncher
)

# UTF-8 WITH BOM is required by Windows PowerShell 5.1 for Chinese text.
$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$ownedServer = $null
$logDirectory = $null
$logStreams = @()
$logCopies = @()
$exitCode = 1
$modelAlias = "HY-MT2-7B-Q8_0"
$baseUrl = "http://127.0.0.1:$Port/v1"

function Write-Status([string]$Message) {
    Write-Host $Message
    if ($logDirectory) {
        [IO.File]::AppendAllText((Join-Path $logDirectory "launcher.log"),
            ((Get-Date -Format "HH:mm:ss") + " " + $Message + [Environment]::NewLine), $utf8)
    }
}

function Test-Header([string]$Path, [byte[]]$Expected) {
    if (-not [IO.File]::Exists($Path)) { return $false }
    $stream = $null
    try {
        $stream = [IO.File]::OpenRead($Path)
        foreach ($b in $Expected) { if ($stream.ReadByte() -ne $b) { return $false } }
        return $true
    } catch { return $false } finally { if ($stream) { $stream.Dispose() } }
}

function Test-ServerFile([string]$Path) {
    return (([IO.Path]::GetFileName($Path) -ieq "llama-server.exe") -and
        (Test-Header $Path ([byte[]](77, 90))))
}

function Resolve-RecordedPath([string]$Path, [string]$Directory) {
    if (-not $Path) { return "" }
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path $Directory $Path))
}

function Select-Candidate([string]$Kind, [string[]]$Candidates) {
    if ($Candidates.Count -eq 1) { return $Candidates[0] }
    Write-Status "找到多个$Kind，默认采用第 1 个："
    for ($i = 0; $i -lt $Candidates.Count; $i++) { Write-Status "  $($i + 1). $($Candidates[$i])" }
    if ($NonInteractive) { return $Candidates[0] }
    while ($true) {
        $answer = Read-Host "输入序号，直接回车采用第 1 个"
        if (-not $answer) { return $Candidates[0] }
        $index = 0
        if ([int]::TryParse($answer, [ref]$index) -and $index -ge 1 -and $index -le $Candidates.Count) {
            return $Candidates[$index - 1]
        }
        Write-Host "请输入上面列出的序号。"
    }
}

function Find-Installation([string[]]$Roots) {
    $servers = New-Object 'System.Collections.Generic.List[string]'
    $models = New-Object 'System.Collections.Generic.List[string]'
    $queue = New-Object 'System.Collections.Generic.Queue[string]'
    $visited = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($root in $Roots) {
        $item = Get-Item -LiteralPath $root -Force
        if (-not $item.PSIsContainer) { throw "扫描位置不是文件夹：$root" }
        $queue.Enqueue($item.FullName)
    }
    $count = 0
    $skipped = 0
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        if (-not $visited.Add($directory)) { continue }
        $count++
        if ($timer.Elapsed.TotalSeconds -ge 3) {
            Write-Status "正在查找：已扫描 $count 个文件夹，跳过 $skipped 个无法访问的文件夹。当前位置：$directory"
            $timer.Restart()
        }
        try { $items = @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop) }
        catch { $skipped++; continue }
        # Only ChickenRice's non-secret installation record is read.
        foreach ($item in $items) {
            if ($item.PSIsContainer -or $item.Name -ine "stage2_runtime.json" -or
                ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
            try {
                $record = [IO.File]::ReadAllText($item.FullName, [Text.Encoding]::UTF8) | ConvertFrom-Json
                $server = Resolve-RecordedPath $record.llama_server_path $directory
                $model = Resolve-RecordedPath $record.model_path $directory
                if ((Test-ServerFile $server) -and ([IO.Path]::GetExtension($model) -ieq ".gguf") -and
                    (Test-Header $model ([byte[]](71, 71, 85, 70)))) {
                    Write-Status "找到海南鸡安装记录：$($item.FullName)"
                    return @{ Server = $server; Model = $model }
                }
                Write-Status "安装记录中的文件已失效，继续查找：$($item.FullName)"
            } catch { Write-Status "安装记录无法读取，继续查找：$($item.FullName)" }
        }
        foreach ($item in $items) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
            if ($item.PSIsContainer) {
                if ($item.Name -notin @('$Recycle.Bin', 'System Volume Information', 'Windows', '_待删')) {
                    $queue.Enqueue($item.FullName)
                }
            } elseif ($item.Name -ieq "llama-server.exe") {
                if (Test-ServerFile $item.FullName) { $servers.Add($item.FullName) }
            } elseif ($item.Name -match '(?i)HY[-_]?MT2.*\.gguf$') {
                if (Test-Header $item.FullName ([byte[]](71, 71, 85, 70))) { $models.Add($item.FullName) }
            }
        }
    }
    Write-Status "查找结束：扫描 $count 个文件夹，跳过 $skipped 个无法访问的文件夹。"
    if ($servers.Count -eq 0 -or $models.Count -eq 0) {
        throw "没有找到完整安装：有效 llama-server.exe 共 $($servers.Count) 个，Hy-MT2 GGUF 共 $($models.Count) 个。请重新运行，选另一个可能安装过的盘（可以一次输入多个盘符）。"
    }
    $model = Select-Candidate "模型" @($models | Sort-Object @{ Expression = { $_ -notmatch '(?i)7B.*Q8[_-]0' } }, { $_ })
    $modelParent = Split-Path -Parent (Split-Path -Parent $model)
    $server = Select-Candidate "服务程序" @($servers | Sort-Object @{ Expression = {
        -not $_.StartsWith(($modelParent.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)
    } }, { $_ })
    return @{ Server = $server; Model = $model }
}

function Get-LocalJson([string]$Url) {
    $response = $null
    try {
        $request = [Net.HttpWebRequest]::Create($Url)
        $request.Proxy = $null
        $request.AllowAutoRedirect = $false
        $request.Timeout = 1500
        $request.ReadWriteTimeout = 1500
        $response = $request.GetResponse()
        $reader = New-Object IO.StreamReader($response.GetResponseStream())
        try { $body = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
        if ([int]$response.StatusCode -ne 200) { return $null }
        return $body
    } catch { return $null } finally { if ($response) { $response.Dispose() } }
    return $null
}

function Get-ReadyModel {
    # llama.cpp's health endpoint remains 503 until the model is loaded.
    $health = Get-LocalJson "http://127.0.0.1:$Port/health"
    if (-not $health -or $health.status -ne "ok") { return $null }
    $body = Get-LocalJson "$baseUrl/models"
    foreach ($model in $body.data) {
        if ($model.id -match '(?i)HY[-_]?MT2') { return [string]$model.id }
    }
    return $null
}

function Test-PortOccupied {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(1000)) { return $false }
        $client.EndConnect($pending)
        return $true
    } catch { return $false } finally { $client.Close() }
}

function Show-ServerErrors {
    if ($ownedServer -and $ownedServer.HasExited) {
        foreach ($copy in $logCopies) { try { $copy.Wait(2000) | Out-Null } catch {} }
    }
    foreach ($stream in $logStreams) { try { $stream.Flush() } catch {} }
    foreach ($name in @("server-stderr.log", "server-stdout.log")) {
        $path = Join-Path $logDirectory $name
        if (Test-Path -LiteralPath $path) {
            Write-Status "--- $name 最后 20 行 ---"
            Get-Content -LiteralPath $path -Encoding UTF8 -Tail 20 | ForEach-Object { Write-Status $_ }
        }
    }
}

try {
    $logParents = @($LogRoot)
    if (-not $LogRoot) {
        $logParents = @((Join-Path $PSScriptRoot "logs"), (Join-Path $env:LOCALAPPDATA "MDCx-HyMT2\logs"))
    }
    foreach ($parent in $logParents) {
        try {
            $candidate = Join-Path $parent ((Get-Date -Format "yyyyMMdd-HHmmss") + "-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
            [IO.Directory]::CreateDirectory($candidate) | Out-Null
            [IO.File]::WriteAllText((Join-Path $candidate "launcher.log"), "", $utf8)
            $logDirectory = $candidate
            break
        } catch { continue }
    }
    if (-not $logDirectory) { throw "无法创建日志文件夹，请将启动包解压到可以写入的文件夹。" }
    Write-Status "MDCx 本机 Hy-MT2 启动器（无需知道模型和程序的具体位置）"
    Write-Status "Log directory: $logDirectory"
    $existing = Get-ReadyModel
    if ($existing) {
        Write-Status "检测到已经就绪的 Hy-MT2 服务：$existing；直接使用，不重复启动。"
    } else {
        if (Test-PortOccupied) { throw "端口 $Port 已被占用，但没有就绪的 Hy-MT2 接口。若海南鸡正在加载模型，请等加载结束后重试；否则请先关闭占用该端口的程序。" }
        if (-not $LlamaServerPath -or -not $ModelPath) {
            if ($LlamaServerPath -or $ModelPath) { throw "高级参数需要同时提供程序和模型；通常只需选择盘符。" }
            if ($SearchRoot.Count -eq 0) {
                if ($NonInteractive) { throw "非交互模式必须指定 SearchRoot。" }
                $drives = @(Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -match '^[A-Za-z]$' })
                Write-Status ("本机可用盘符：" + (($drives | ForEach-Object { $_.Name + ':' }) -join '  '))
                while ($SearchRoot.Count -eq 0) {
                    $answer = (Read-Host "输入大概安装在哪个盘，例如 H；不确定可输入 D E H").Trim()
                    $tokens = @($answer -split '[,，;；\s]+' | Where-Object { $_ })
                    if ($tokens.Count -eq 0) { continue }
                    $valid = $true
                    $roots = @()
                    foreach ($token in $tokens) {
                        if ($token -notmatch '^[A-Za-z]:?[\\/]?$') { $valid = $false; break }
                        $root = $token.Substring(0, 1).ToUpper() + ':\'
                        if (-not [IO.Directory]::Exists($root)) { $valid = $false; break }
                        $roots += $root
                    }
                    if ($valid) { $SearchRoot = $roots } else { Write-Host "请输入存在的盘符，例如 D 或 D E。" }
                }
            }
            Write-Status ("开始查找：" + ($SearchRoot -join ', ') + "。只查找安装位置，大盘可能需要几分钟。")
            $installation = Find-Installation $SearchRoot
            $LlamaServerPath = $installation.Server
            $ModelPath = $installation.Model
        }
        if (-not (Test-ServerFile $LlamaServerPath)) { throw "服务程序不存在或不是有效的 llama-server.exe：$LlamaServerPath" }
        if ([IO.Path]::GetExtension($ModelPath) -ine '.gguf' -or -not (Test-Header $ModelPath ([byte[]](71, 71, 85, 70)))) {
            throw "模型不存在或不是有效的 GGUF 文件：$ModelPath"
        }
        $LlamaServerPath = (Get-Item -LiteralPath $LlamaServerPath).FullName
        $ModelPath = (Get-Item -LiteralPath $ModelPath).FullName
        Write-Status "服务程序：$LlamaServerPath"
        Write-Status "模型文件：$ModelPath"
        Write-Status "正在启动模型，首次加载可能需要几分钟……"
        # Use literal .NET paths: PS 5.1 Start-Process treats [] as wildcards.
        $serverArguments = '-m "' + $ModelPath + '" -ngl 999 -c 8192 --host 127.0.0.1 --port ' + $Port + ' --alias ' + $modelAlias
        $info = New-Object Diagnostics.ProcessStartInfo
        $info.FileName = $LlamaServerPath
        $info.Arguments = $serverArguments
        $info.WorkingDirectory = [IO.Path]::GetDirectoryName($LlamaServerPath)
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        foreach ($name in @("server-stdout.log", "server-stderr.log")) {
            $logStreams += [IO.File]::Open((Join-Path $logDirectory $name),
                [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::Read)
        }
        $process = New-Object Diagnostics.Process
        $process.StartInfo = $info
        try {
            if (-not $process.Start()) { throw "Windows 未能启动服务程序。" }
        } catch { $process.Dispose(); throw }
        $ownedServer = $process
        # Drain both pipes asynchronously without PowerShell callbacks/runspaces.
        $logCopies += $ownedServer.StandardOutput.BaseStream.CopyToAsync($logStreams[0])
        $logCopies += $ownedServer.StandardError.BaseStream.CopyToAsync($logStreams[1])
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $lastProgress = 0
        while ($true) {
            $ownedServer.Refresh()
            if ($ownedServer.HasExited) { throw "llama-server 提前退出，退出码：$($ownedServer.ExitCode)。请查看下面的服务日志。" }
            $readyModel = Get-ReadyModel
            if ($readyModel) {
                $ownedServer.Refresh()
                if ($ownedServer.HasExited) { throw "服务启动过程中已退出。" }
                break
            }
            if ($timer.Elapsed.TotalSeconds -ge $StartupTimeoutSeconds) { throw "等待模型加载超时（$StartupTimeoutSeconds 秒）。服务日志保存在下方目录，可检查显存不足、驱动或依赖错误。" }
            if ($timer.Elapsed.TotalSeconds -ge ($lastProgress + 10)) {
                $lastProgress = [int]$timer.Elapsed.TotalSeconds
                Write-Status "仍在加载模型，已等待 $lastProgress 秒……"
            }
            Start-Sleep -Milliseconds 500
        }
    }
    Write-Status "服务已就绪：$baseUrl"
    if ($existing -and $existing -cne $modelAlias) {
        Write-Status "该服务模型名为 $existing，请在 MDCx 主模型一栏填写这个名称。"
    }
    Write-Status "打开 MDCx：设置 → 翻译 → 本机 Hy-MT2 预设 → 保存，然后开始刮削。"
    if (-not $NonInteractive) {
        if ($ownedServer) {
            Write-Status "使用期间保持本窗口打开；结束后在本窗口按回车，停止本次启动的模型并释放显存。"
            Read-Host "使用结束后按回车停止" | Out-Null
        } else { Write-Status "现有服务由其他程序管理，本启动器不会关闭它。" }
    }
    $exitCode = 0
} catch {
    Write-Host ""
    Write-Status ("启动失败：" + $_.Exception.Message)
    if ($logDirectory) { Show-ServerErrors; Write-Status "完整日志：$logDirectory" }
} finally {
    if ($ownedServer) {
        try {
            if (-not $ownedServer.HasExited) {
                Stop-Process -Id $ownedServer.Id -Force -ErrorAction Stop
                $ownedServer.WaitForExit(5000) | Out-Null
            }
            Write-Status "本次启动的模型服务已停止。"
        } catch { Write-Host "停止服务时遇到错误：$($_.Exception.Message)" }
        $ownedServer.Dispose()
    }
    foreach ($copy in $logCopies) { try { $copy.Wait(5000) | Out-Null } catch {} }
    foreach ($stream in $logStreams) { $stream.Dispose() }
}

if (-not $NonInteractive -and -not $FromLauncher) {
    Write-Host "按回车关闭窗口"
    Read-Host | Out-Null
}
exit $exitCode
