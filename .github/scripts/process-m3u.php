<?php
echo "Processing M3U files...\n";

$raw_dir = __DIR__ . '/../../raw_m3u';
$files = glob($raw_dir . '/*.m3u');

if (empty($files)) {
    echo "No M3U files found\n";
    exit(0);
}

echo "Found " . count($files) . " file(s)\n";

// Create processed directory
$proc_dir = __DIR__ . '/../../processed';
if (!is_dir($proc_dir)) {
    mkdir($proc_dir, 0755, true);
}

// Simple output
$output = [
    'files' => $files,
    'processed_at' => date('Y-m-d H:i:s'),
    'note' => 'Replace with real parser'
];

file_put_contents($proc_dir . '/output.json', json_encode($output, JSON_PRETTY_PRINT));
echo "Done\n";
?>
