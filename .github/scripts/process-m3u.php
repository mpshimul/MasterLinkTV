<?php
echo "=== Processing BD.m3u ===\n";

require_once 'M3UParser.php';

$parser = new M3UParser();
$bd_file = __DIR__ . '/../../raw_m3u/BD.m3u';
$processed_dir = __DIR__ . '/../../processed';

if (!file_exists($bd_file)) {
    echo "❌ BD.m3u not found!\n";
    exit(1);
}

// Process BD.m3u
try {
    $channels = $parser->processFile($bd_file);
    echo "Found: " . count($channels) . " channel entries\n";
    
    // Group by duplicate channels
    $grouped_channels = $parser->groupChannelsByDuplicate($channels);
    
    // Add proxy URLs to each server
    $grouped_channels = addProxyToChannels($grouped_channels, 'https://your-domain.com/path-to-proxy/');
    
    // Save data
    if (!is_dir($processed_dir)) {
        mkdir($processed_dir, 0755, true);
    }
    
    // Create statistics
    $stats = [
        'total_entries' => count($channels),
        'unique_channels' => count($grouped_channels),
        'channels_with_multiple_servers' => 0,
        'total_servers' => 0,
        'channels_with_headers' => 0,
        'groups' => [],
        'last_updated' => date('c'),
        'source' => 'BD.m3u'
    ];
    
    foreach ($grouped_channels as $channel_id => $channel) {
        $stats['total_servers'] += count($channel['servers']);
        
        if (count($channel['servers']) > 1) {
            $stats['channels_with_multiple_servers']++;
        }
        
        // Check if any server has headers
        foreach ($channel['servers'] as $server) {
            if (!empty($server['headers'])) {
                $stats['channels_with_headers']++;
                break;
            }
        }
        
        // Count by group
        $group = $channel['group'];
        if (!isset($stats['groups'][$group])) {
            $stats['groups'][$group] = 0;
        }
        $stats['groups'][$group]++;
    }
    
    // Save grouped channels in your desired format
    $data = [
        'statistics' => $stats,
        'channels' => $grouped_channels,
        'metadata' => [
            'version' => '2.0',
            'format' => 'channel-grouped',
            'last_updated' => date('c')
        ]
    ];
    
    file_put_contents(
        $processed_dir . '/bd_channels.json',
        json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    // Also save a simplified version for easy access
    $simple_data = createSimpleFormat($grouped_channels);
    file_put_contents(
        $processed_dir . '/channels.json',
        json_encode($simple_data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    echo "\n✅ Processing complete!\n";
    echo "📊 Statistics:\n";
    echo "   • Total entries: " . $stats['total_entries'] . "\n";
    echo "   • Unique channels: " . $stats['unique_channels'] . "\n";
    echo "   • Total servers: " . $stats['total_servers'] . "\n";
    echo "   • Channels with multiple servers: " . $stats['channels_with_multiple_servers'] . "\n";
    echo "   • Channels with headers: " . $stats['channels_with_headers'] . "\n";
    echo "   • Groups: " . count($stats['groups']) . "\n";
    
    // Show examples
    echo "\n🎯 Example channels with multiple servers:\n";
    $examples = 0;
    foreach ($grouped_channels as $channel_id => $channel) {
        if (count($channel['servers']) > 1) {
            echo "   • " . $channel['name'] . " - " . count($channel['servers']) . " servers\n";
            $examples++;
            if ($examples >= 5) break;
        }
    }
    
} catch (Exception $e) {
    echo "❌ Error: " . $e->getMessage() . "\n";
    exit(1);
}

// Function to add proxy URLs
function addProxyToChannels($grouped_channels, $proxy_base_url) {
    foreach ($grouped_channels as &$channel) {
        foreach ($channel['servers'] as &$server) {
            // Build proxy URL
            $proxy_url = $proxy_base_url . 'proxy.php?url=' . urlencode($server['url']);
            
            // Add headers as parameters
            if (!empty($server['headers'])) {
                foreach ($server['headers'] as $key => $value) {
                    $param_name = strtolower(str_replace('-', '_', $key));
                    if (in_array($param_name, ['user_agent', 'referer', 'origin', 'cookie'])) {
                        $proxy_url .= '&' . $param_name . '=' . urlencode($value);
                    } else {
                        $proxy_url .= '&header_' . $param_name . '=' . urlencode($value);
                    }
                }
            }
            
            $server['proxy_url'] = $proxy_url;
        }
    }
    
    return $grouped_channels;
}

// Function to create simplified format
function createSimpleFormat($grouped_channels) {
    $simple = [];
    
    foreach ($grouped_channels as $channel_id => $channel) {
        $simple[$channel_id] = [
            'name' => $channel['name'],
            'logo' => $channel['logo'],
            'group' => $channel['group'],
            'servers' => array_map(function($server) {
                return [
                    'url' => $server['proxy_url'] ?? $server['url'],
                    'quality' => $server['quality'],
                    'priority' => $server['priority'],
                    'has_headers' => !empty($server['headers']),
                    'server_number' => $server['server_number']
                ];
            }, $channel['servers'])
        ];
    }
    
    return $simple;
}
?>