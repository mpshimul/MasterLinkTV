<?php
// process-m3u.php - Add debug output

require_once 'M3UParser.php';

echo "=== Starting M3U Processing ===\n";

$RAW_DIR = __DIR__ . '/../../raw_m3u';
$PROCESSED_DIR = __DIR__ . '/../../processed';

// Create directories if needed
if (!is_dir($RAW_DIR)) mkdir($RAW_DIR, 0755, true);
if (!is_dir($PROCESSED_DIR)) mkdir($PROCESSED_DIR, 0755, true);

$parser = new M3UParser();
$m3u_files = glob($RAW_DIR . '/*.m3u');

echo "Found " . count($m3u_files) . " M3U file(s):\n";

$all_channels = [];
$file_results = [];

foreach ($m3u_files as $file_path) {
    $filename = basename($file_path);
    echo "\n📁 Processing: $filename\n";
    
    try {
        $result = $parser->processFile($file_path);
        $file_results[$filename] = $result;
        
        // Add source file info
        foreach ($result['channels'] as &$channel) {
            $channel['source_file'] = $filename;
            
            // DEBUG: Show what was parsed
            echo "  📺 " . $channel['name'] . "\n";
            echo "     Group: " . $channel['group'] . "\n";
            echo "     Logo: " . ($channel['logo'] ? 'Yes' : 'No') . "\n";
            echo "     Headers: " . (empty($channel['headers']) ? 'No' : 'Yes') . "\n";
        }
        
        $all_channels = array_merge($all_channels, $result['channels']);
        
        echo "  ✅ Found " . $result['total_channels'] . " channels\n";
        
    } catch (Exception $e) {
        echo "  ❌ Error: " . $e->getMessage() . "\n";
    }
}

// Process all channels
if (!empty($all_channels)) {
    echo "\n=== Processing all channels ===\n";
    
    $combined_result = $parser->processAllChannels($all_channels);
    $combined_result['processed_at'] = date('c');
    $combined_result['source_files'] = array_keys($file_results);
    
    // Save files
    file_put_contents(
        $PROCESSED_DIR . '/channels.json',
        json_encode($combined_result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    // Save light version
    $light_version = [
        'channels' => $combined_result['channels'],
        'total_channels' => $combined_result['total_channels'],
        'last_updated' => $combined_result['processed_at']
    ];
    
    file_put_contents(
        $PROCESSED_DIR . '/channels_light.json',
        json_encode($light_version, JSON_UNESCAPED_SLASHES)
    );
    
    // Save groups
    file_put_contents(
        $PROCESSED_DIR . '/groups.json',
        json_encode($combined_result['groups'], JSON_PRETTY_PRINT)
    );
    
    // Save duplicates
    file_put_contents(
        $PROCESSED_DIR . '/duplicates.json',
        json_encode($combined_result['duplicates'], JSON_PRETTY_PRINT)
    );
    
    echo "\n✅ Processing complete!\n";
    echo "Total channels: " . $combined_result['total_channels'] . "\n";
    echo "Unique channels: " . $combined_result['unique_channels'] . "\n";
    echo "Groups found: " . count($combined_result['groups']) . "\n";
    
    echo "\n📊 Groups breakdown:\n";
    foreach ($combined_result['groups'] as $group => $count) {
        echo "  - $group: $count channels\n";
    }
    
} else {
    echo "\n❌ No channels processed!\n";
}
?>
