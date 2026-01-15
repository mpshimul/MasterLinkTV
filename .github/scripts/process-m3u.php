<?php
echo "=== Processing ONLY BD.m3u ===\n";

require_once 'M3UParser.php';

$parser = new M3UParser();
$bd_file = __DIR__ . '/../../raw_m3u/BD.m3u';
$processed_dir = __DIR__ . '/../../processed';

if (!file_exists($bd_file)) {
    echo "❌ BD.m3u not found!\n";
    exit(1);
}

// Process ONLY BD.m3u
try {
    $result = $parser->processFile($bd_file);
    $channel_count = count($result['channels']);
    
    echo "Found: $channel_count channels in BD.m3u\n";
    
    // Process for duplicates within BD.m3u only
    $combined = $parser->processAllChannels($result['channels']);
    
    // Save data
    if (!is_dir($processed_dir)) {
        mkdir($processed_dir, 0755, true);
    }
    
    // Save only BD channels
    $data = [
        'channels' => $combined['channels'],
        'total_channels' => $channel_count,
        'unique_channels' => $combined['unique_channels'],
        'duplicates_in_file' => $combined['duplicate_count'],
        'source' => 'BD.m3u only',
        'url' => 'https://github.com/abusaeeidx/IPTV-Scraper-Zilla/blob/main/BD.m3u',
        'last_updated' => date('c')
    ];
    
    file_put_contents(
        $processed_dir . '/bd_channels.json',
        json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    echo "✅ Saved $channel_count channels from BD.m3u\n";
    echo "   • Unique: " . $combined['unique_channels'] . "\n";
    echo "   • Duplicates within file: " . $combined['duplicate_count'] . "\n";
    
} catch (Exception $e) {
    echo "❌ Error: " . $e->getMessage() . "\n";
}
?>
