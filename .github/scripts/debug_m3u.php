<?php
// debug_m3u.php - Debug M3U file format

$filepath = __DIR__ . '/../../raw_m3u/BD.m3u';

if (!file_exists($filepath)) {
    die("File not found: BD.m3u\n");
}

echo "=== Analyzing BD.m3u ===\n";
echo "File size: " . filesize($filepath) . " bytes\n\n";

$content = file_get_contents($filepath);
$lines = explode("\n", $content);

echo "First 10 lines:\n";
for ($i = 0; $i < min(10, count($lines)); $i++) {
    echo "Line $i: " . substr(trim($lines[$i]), 0, 100) . "\n";
}

echo "\n=== Looking for EXTINF lines ===\n";
$extinf_count = 0;

foreach ($lines as $line_num => $line) {
    $line = trim($line);
    
    if (strpos($line, '#EXTINF:') === 0) {
        $extinf_count++;
        echo "\nEXTINF #$extinf_count (Line $line_num):\n";
        echo "Full line: " . substr($line, 0, 150) . "\n";
        
        // Check for group-title
        if (preg_match('/group-title="([^"]+)"/', $line, $match)) {
            echo "✓ Found group: " . $match[1] . "\n";
        } else {
            echo "✗ No group-title attribute\n";
            
            // Check other formats
            if (preg_match('/group-title=([^ ,]+)/', $line, $match)) {
                echo "  Alternative group: " . $match[1] . "\n";
            }
        }
        
        // Check for tvg-logo
        if (preg_match('/tvg-logo="([^"]+)"/', $line, $match)) {
            echo "✓ Logo: " . $match[1] . "\n";
        }
        
        // Extract channel name
        $last_comma = strrpos($line, ',');
        if ($last_comma !== false) {
            $name = trim(substr($line, $last_comma + 1));
            echo "Channel name: " . $name . "\n";
        }
    }
}

echo "\n=== Summary ===\n";
echo "Total lines: " . count($lines) . "\n";
echo "EXTINF lines found: $extinf_count\n";

// Count URLs
$url_count = 0;
foreach ($lines as $line) {
    $line = trim($line);
    if (!empty($line) && !str_starts_with($line, '#')) {
        $url_count++;
    }
}
echo "URL lines: $url_count\n";
?>
