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

// Debug mode
$debug = true;

// Process BD.m3u
try {
    $channels = $parser->processFile($bd_file);
    echo "Found: " . count($channels) . " channel entries\n";
    
    if ($debug) {
        echo "\n=== DEBUG: Sample channels with headers ===\n";
        $header_count = 0;
        for ($i = 0; $i < min(10, count($channels)); $i++) {
            if (!empty($channels[$i]['headers'])) {
                echo "Channel #" . ($i+1) . ": " . $channels[$i]['name'] . "\n";
                echo "Headers: " . json_encode($channels[$i]['headers']) . "\n";
                echo "URL: " . substr($channels[$i]['url'], 0, 80) . "...\n";
                echo "---\n";
                $header_count++;
            }
        }
        echo "Channels with headers in sample: $header_count\n";
    }
    
    // Group by duplicate channels
    $grouped_channels = $parser->groupChannelsByDuplicate($channels);
    
    // Add proxy URLs
    $proxy_base_url = 'https://your-server.com/proxy.php?';
    $grouped_channels = addProxyToChannels($grouped_channels, $proxy_base_url);
    
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
        'total_headers' => 0,
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
        
        // Count channels with headers
        foreach ($channel['servers'] as $server) {
            if (!empty($server['headers'])) {
                $stats['channels_with_headers']++;
                $stats['total_headers'] += count($server['headers']);
                break;
            }
        }
        
        $group = $channel['group'];
        if (!isset($stats['groups'][$group])) {
            $stats['groups'][$group] = 0;
        }
        $stats['groups'][$group]++;
    }
    
    // Save simple format for players
    $simple_data = createSimpleFormat($grouped_channels);
    file_put_contents(
        $processed_dir . '/channels.json',
        json_encode($simple_data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    // Save full data with statistics
    $full_data = [
        'statistics' => $stats,
        'channels' => $grouped_channels,
        'metadata' => [
            'version' => '2.0',
            'format' => 'grouped',
            'last_updated' => date('c')
        ]
    ];
    
    file_put_contents(
        $processed_dir . '/bd_channels.json',
        json_encode($full_data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    // Save summary
    file_put_contents(
        $processed_dir . '/summary.json',
        json_encode($stats, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)
    );
    
    echo "\n✅ Processing complete!\n";
    echo "📊 Statistics:\n";
    echo "   • Total entries: " . $stats['total_entries'] . "\n";
    echo "   • Unique channels: " . $stats['unique_channels'] . "\n";
    echo "   • Total servers: " . $stats['total_servers'] . "\n";
    echo "   • Channels with multiple servers: " . $stats['channels_with_multiple_servers'] . "\n";
    echo "   • Channels with headers: " . $stats['channels_with_headers'] . "\n";
    echo "   • Total headers found: " . $stats['total_headers'] . "\n";
    echo "   • Groups: " . count($stats['groups']) . "\n";
    
    // Show top 10 groups
    echo "\n🏷️ Top 10 Groups:\n";
    arsort($stats['groups']);
    $count = 0;
    foreach ($stats['groups'] as $group => $group_count) {
        echo "   • $group: $group_count channels\n";
        $count++;
        if ($count >= 10) break;
    }
    
    // Show example output
    echo "\n🎯 Example channel with headers:\n";
    $found_example = false;
    foreach ($grouped_channels as $channel) {
        foreach ($channel['servers'] as $server) {
            if (!empty($server['headers'])) {
                echo "   • " . $channel['name'] . " (" . $channel['group'] . ")\n";
                echo "     Headers: " . count($server['headers']) . "\n";
                echo "     Proxy URL: " . substr($server['proxy_url'] ?? '', 0, 100) . "...\n";
                $found_example = true;
                break 2;
            }
        }
    }
    
    if (!$found_example) {
        echo "   No channels with headers found!\n";
    }
    
} catch (Exception $e) {
    echo "❌ Error: " . $e->getMessage() . "\n";
    exit(1);
}

function addProxyToChannels($grouped_channels, $proxy_base_url) {
    foreach ($grouped_channels as &$channel) {
        foreach ($channel['servers'] as &$server) {
            $proxy_url = $proxy_base_url . 'url=' . urlencode($server['url']);
            
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

function createSimpleFormat($grouped_channels) {
    $simple = [];
    
    foreach ($grouped_channels as $channel_key => $channel) {
        // Skip if name is empty
        if (empty(trim($channel['name']))) {
            continue;
        }
        
        $simple_channel = [
            'name' => $channel['name'],
            'logo' => $channel['logo'] ?? '',
            'group' => $channel['group'] ?? 'Uncategorized',
            'servers' => []
        ];
        
        foreach ($channel['servers'] as $server) {
            $simple_channel['servers'][] = [
                'url' => $server['proxy_url'] ?? $server['url'],
                'quality' => $server['quality'] ?? 'Unknown',
                'priority' => $server['priority'] ?? 1,
                'has_headers' => !empty($server['headers']),
                'headers_count' => count($server['headers'] ?? []),
                'server_number' => $server['server_number']
            ];
        }
        
        // Generate clean key
        $key = generateChannelKey($channel['name'], $channel['group']);
        $simple[$key] = $simple_channel;
    }
    
    return $simple;
}

function generateChannelKey($name, $group = '') {
    $key = strtolower($name);
    $key = preg_replace('/[^a-z0-9]/', '_', $key);
    $key = preg_replace('/_+/', '_', $key);
    $key = trim($key, '_');
    
    if (!empty($group)) {
        $group_key = strtolower($group);
        $group_key = preg_replace('/[^a-z0-9]/', '_', $group_key);
        $group_key = preg_replace('/_+/', '_', $group_key);
        $group_key = trim($group_key, '_');
        $key = $key . '_' . $group_key;
    }
    
    if (empty($key)) {
        $key = 'channel_' . substr(md5($name . $group), 0, 8);
    }
    
    return $key;
}
?>