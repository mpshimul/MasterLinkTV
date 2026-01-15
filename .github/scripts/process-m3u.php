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

// Process BD.m3u
try {
    $channels = $parser->processFile($bd_file);
    echo "Found: " . count($channels) . " channel entries\n";
    
    // Group by duplicate channels
    $grouped_channels = $parser->groupChannelsByDuplicate($channels);
    
    // Add proxy URLs
    $grouped_channels = $this->addProxyToChannels($grouped_channels, 'https://your-domain.com/path-to-proxy/');
    
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
        'groups' => [],
        'last_updated' => date('c'),
        'source' => 'BD.m3u',
        'url' => 'https://github.com/abusaeeidx/IPTV-Scraper-Zilla/blob/main/BD.m3u'
    ];
    
    foreach ($grouped_channels as $channel) {
        $stats['total_servers'] += count($channel['servers']);
        
        if (count($channel['servers']) > 1) {
            $stats['channels_with_multiple_servers']++;
        }
        
        $group = $channel['group'];
        if (!isset($stats['groups'][$group])) {
            $stats['groups'][$group] = 0;
        }
        $stats['groups'][$group]++;
    }
    
    // Save grouped channels
    $data = [
        'statistics' => $stats,
        'channels' => $grouped_channels,
        'metadata' => [
            'version' => '1.0',
            'format' => 'grouped',
            'last_updated' => date('c')
        ]
    ];
    
    file_put_contents(
        $processed_dir . '/bd_channels_grouped.json',
        json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    // Also save a simplified version for players
    $simple_data = $this->createSimpleFormat($grouped_channels);
    file_put_contents(
        $processed_dir . '/bd_channels_simple.json',
        json_encode($simple_data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    echo "✅ Processing complete!\n";
    echo "   • Unique channels: " . $stats['unique_channels'] . "\n";
    echo "   • Total servers: " . $stats['total_servers'] . "\n";
    echo "   • Channels with multiple servers: " . $stats['channels_with_multiple_servers'] . "\n";
    echo "   • Groups: " . count($stats['groups']) . "\n";
    
    // Print summary by group
    echo "\n📊 Group Summary:\n";
    foreach ($stats['groups'] as $group => $count) {
        echo "   • $group: $count channels\n";
    }
    
} catch (Exception $e) {
    echo "❌ Error: " . $e->getMessage() . "\n";
    exit(1);
}

// Function to add proxy URLs
function addProxyToChannels($grouped_channels, $proxy_base_url) {
    foreach ($grouped_channels as &$channel) {
        foreach ($channel['servers'] as &$server) {
            $proxy_url = $proxy_base_url . 'proxy.php?url=' . urlencode($server['url']);
            
            // Add headers as parameters
            if (!empty($server['headers'])) {
                foreach ($server['headers'] as $key => $value) {
                    $param_name = strtolower(str_replace('-', '_', $key));
                    if (in_array($param_name, ['user_agent', 'referer', 'origin'])) {
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
    $simple = [
        'channels' => [],
        'groups' => []
    ];
    
    foreach ($grouped_channels as $channel_key => $channel) {
        $simple_channel = [
            'id' => $channel['id'],
            'name' => $channel['name'],
            'logo' => $channel['logo'],
            'group' => $channel['group'],
            'quality' => $channel['quality'],
            'server_count' => count($channel['servers']),
            'servers' => []
        ];
        
        foreach ($channel['servers'] as $server) {
            $simple_channel['servers'][] = [
                'id' => $server['id'],
                'priority' => $server['priority'],
                'quality' => $server['quality'],
                'has_headers' => !empty($server['headers']),
                'url' => $server['proxy_url'] ?? $server['url'],
                'server_number' => $server['server_number']
            ];
        }
        
        $simple['channels'][$channel['id']] = $simple_channel;
        
        // Add to groups
        if (!isset($simple['groups'][$channel['group']])) {
            $simple['groups'][$channel['group']] = [];
        }
        $simple['groups'][$channel['group']][] = $channel['id'];
    }
    
    return $simple;
}
?>