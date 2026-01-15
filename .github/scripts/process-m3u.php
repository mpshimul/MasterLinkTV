
<?php
// .github/scripts/process-m3u.php
// Runs on GitHub Actions to process M3U to JSON

require_once __DIR__ . '/M3UParser.php';

$parser = new M3UParser();
$result = $parser->processFile('BD.m3u');

// Create processed directory
if (!is_dir('processed')) {
    mkdir('processed');
}

// Save full JSON
file_put_contents('processed/channels.json', json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

// Save simplified versions
file_put_contents('processed/channels_light.json', json_encode([
    'channels' => $result['channels'],
    'last_updated' => $result['last_updated'],
    'total' => $result['total_channels']
], JSON_UNESCAPED_SLASHES));

// Save groups index
file_put_contents('processed/groups.json', json_encode($result['groups'], JSON_PRETTY_PRINT));

// Save duplicates info
file_put_contents('processed/duplicates.json', json_encode($result['duplicates'], JSON_PRETTY_PRINT));

echo "Processed " . $result['total_channels'] . " channels\n";
echo "Found " . count($result['duplicates']) . " duplicate channels\n";
?>
