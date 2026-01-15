<?php
// process-m3u.php - GitHub Action processing script
// Updated for proper file paths

echo "=== Starting M3U Processing ===\n";

// Define paths
$RAW_DIR = __DIR__ . '/../../raw_m3u';
$PROCESSED_DIR = __DIR__ . '/../../processed';

// Check if raw_m3u directory exists
if (!is_dir($RAW_DIR)) {
    echo "ERROR: raw_m3u directory not found!\n";
    echo "Creating raw_m3u directory...\n";
    mkdir($RAW_DIR, 0755, true);
    
    // Create a sample M3U file for testing
    $sample_m3u = "#EXTM3U\n#EXTINF:-1 tvg-logo=\"https://example.com/logo.png\" group-title=\"Test\",Test Channel\nhttp://example.com/test.m3u8\n";
    file_put_contents($RAW_DIR . '/sample.m3u', $sample_m3u);
    echo "Created sample.m3u for testing\n";
}

// Check if processed directory exists
if (!is_dir($PROCESSED_DIR)) {
    echo "Creating processed directory...\n";
    mkdir($PROCESSED_DIR, 0755, true);
}

// Include parser
require_once 'M3UParser.php';

$parser = new M3UParser();

// Get all M3U files
$m3u_files = glob($RAW_DIR . '/*.m3u');
echo "Found " . count($m3u_files) . " M3U file(s):\n";

foreach ($m3u_files as $file) {
    echo "- " . basename($file) . "\n";
}

if (empty($m3u_files)) {
    echo "No M3U files found in raw_m3u/\n";
    echo "Please add your M3U files to the raw_m3u/ directory\n";
    
    // Create a placeholder JSON file
    $placeholder = [
        'success' => false,
        'error' => 'No M3U files found',
        'channels' => [],
        'total_channels' => 0,
        'last_updated' => date('c'),
        'note' => 'Add M3U files to raw_m3u/ directory'
    ];
    
    file_put_contents($PROCESSED_DIR . '/channels.json', json_encode($placeholder, JSON_PRETTY_PRINT));
    exit(0);
}

// Process each file
$all_channels = [];
$file_results = [];

foreach ($m3u_files as $file_path) {
    $filename = basename($file_path);
    echo "\nProcessing: $filename\n";
    
    try {
        $result = $parser->processFile($file_path);
        $file_results[$filename] = $result;
        
        // Add source file info to each channel
        foreach ($result['channels'] as &$channel) {
            $channel['source_file'] = $filename;
        }
        
        // Merge channels
        $all_channels = array_merge($all_channels, $result['channels']);
        
        echo "  ✓ Found " . $result['total_channels'] . " channels\n";
        echo "  ✓ " . count($result['groups'] ?? []) . " groups\n";
        
    } catch (Exception $e) {
        echo "  ✗ Error: " . $e->getMessage() . "\n";
        $file_results[$filename] = [
            'error' => $e->getMessage(),
            'success' => false
        ];
    }
}

// Process all channels together for duplicate detection
if (!empty($all_channels)) {
    $combined_result = $parser->processAllChannels($all_channels);
    
    echo "\n=== Combined Results ===\n";
    echo "Total channels: " . $combined_result['total_channels'] . "\n";
    echo "Unique channels: " . $combined_result['unique_channels'] . "\n";
    echo "Duplicate channels: " . $combined_result['duplicate_count'] . "\n";
    echo "Groups: " . count($combined_result['groups'] ?? []) . "\n";
    
    // Save full combined result
    $combined_result['processed_at'] = date('c');
    $combined_result['source_files'] = array_keys($file_results);
    
    file_put_contents(
        $PROCESSED_DIR . '/channels.json',
        json_encode($combined_result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    // Save light version (channels only)
    $light_version = [
        'channels' => $combined_result['channels'],
        'total_channels' => $combined_result['total_channels'],
        'last_updated' => $combined_result['processed_at'],
        'source_files' => $combined_result['source_files']
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
    echo "Files saved to processed/ directory:\n";
    echo "- channels.json (full data)\n";
    echo "- channels_light.json (lightweight)\n";
    echo "- groups.json (group statistics)\n";
    echo "- duplicates.json (duplicate info)\n";
    
} else {
    echo "\n❌ No channels were processed!\n";
    
    $error_data = [
        'success' => false,
        'error' => 'No channels processed',
        'file_results' => $file_results,
        'processed_at' => date('c')
    ];
    
    file_put_contents(
        $PROCESSED_DIR . '/channels.json',
        json_encode($error_data, JSON_PRETTY_PRINT)
    );
}
?>
