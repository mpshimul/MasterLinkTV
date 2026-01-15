<?php
// process-m3u.php - Process external M3U sources

require_once 'M3UParser.php';

echo "=== M3U Processor ===\n";

$parser = new M3UParser();
$raw_dir = __DIR__ . '/../../raw_m3u';
$processed_dir = __DIR__ . '/../../processed';

// Create directories
if (!is_dir($processed_dir)) {
    mkdir($processed_dir, 0755, true);
}

// Get all M3U files (including external_source.m3u)
$files = glob($raw_dir . '/*.m3u');
echo "Found " . count($files) . " M3U file(s)\n";

if (empty($files)) {
    echo "No M3U files found. The fetch step may have failed.\n";
    
    // Create empty data
    $empty_data = [
        'channels' => [],
        'total' => 0,
        'updated' => date('c'),
        'note' => 'No data available. Check fetch workflow.'
    ];
    
    file_put_contents($processed_dir . '/channels_light.json', 
        json_encode($empty_data, JSON_UNESCAPED_SLASHES));
    exit(0);
}

// Process each file
$all_channels = [];
$sources = [];

foreach ($files as $file) {
    $filename = basename($file);
    echo "\n📁 Processing: $filename\n";
    
    try {
        $result = $parser->processFile($file);
        
        // Add source info
        foreach ($result['channels'] as &$channel) {
            $channel['source_file'] = $filename;
            $channel['source_type'] = ($filename === 'external_source.m3u') ? 'external' : 'local';
        }
        
        $all_channels = array_merge($all_channels, $result['channels']);
        $sources[] = $filename;
        
        echo "  ✅ " . count($result['channels']) . " channels\n";
        
    } catch (Exception $e) {
        echo "  ❌ Error: " . $e->getMessage() . "\n";
    }
}

// Process all channels
if (!empty($all_channels)) {
    echo "\n=== Final Processing ===\n";
    
    $combined = $parser->processAllChannels($all_channels);
    $combined['processed_at'] = date('c');
    $combined['sources'] = $sources;
    $combined['external_source'] = 'https://github.com/abusaeeidx/IPTV-Scraper-Zilla';
    
    // Save full data
    file_put_contents(
        $processed_dir . '/channels.json',
        json_encode($combined, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    // Save light version
    $light = [
        'channels' => $combined['channels'],
        'total' => $combined['total_channels'],
        'updated' => $combined['processed_at'],
        'sources' => $sources,
        'external' => true
    ];
    
    file_put_contents(
        $processed_dir . '/channels_light.json',
        json_encode($light, JSON_UNESCAPED_SLASHES)
    );
    
    // Save stats
    $stats = [
        'total_channels' => $combined['total_channels'],
        'unique_channels' => $combined['unique_channels'],
        'groups' => count($combined['groups']),
        'duplicates' => $combined['duplicate_count'],
        'last_updated' => $combined['processed_at']
    ];
    
    file_put_contents(
        $processed_dir . '/stats.json',
        json_encode($stats, JSON_PRETTY_PRINT)
    );
    
    echo "🎉 Processing Complete!\n";
    echo "📊 Statistics:\n";
    echo "  • Total channels: " . $combined['total_channels'] . "\n";
    echo "  • Unique channels: " . $combined['unique_channels'] . "\n";
    echo "  • Groups: " . count($combined['groups']) . "\n";
    echo "  • Duplicates: " . $combined['duplicate_count'] . "\n";
    echo "  • Sources: " . implode(', ', $sources) . "\n";
    
} else {
    echo "\n❌ No channels processed!\n";
}
?>
