<?php
// M3UParser.php - Improved parser with better attribute handling

class M3UParser {
    
    public function processFile($filepath) {
        if (!file_exists($filepath)) {
            throw new Exception("File not found: " . basename($filepath));
        }
        
        $content = file_get_contents($filepath);
        return $this->parse($content, basename($filepath));
    }
    
    public function parse($m3uContent, $source_filename = 'unknown') {
        $lines = explode("\n", $m3uContent);
        $channels = [];
        $groups = [];
        $current = null;
        
        foreach ($lines as $line) {
            $line = trim($line);
            if (empty($line)) continue;
            
            // EXTINF line
            if (strpos($line, '#EXTINF:') === 0) {
                $current = $this->parseExtinf($line);
                $current['source_file'] = $source_filename;
            }
            // EXTVLCOPT headers
            elseif (strpos($line, '#EXTVLCOPT:') === 0 && $current) {
                $this->parseVlcOpt($line, $current);
            }
            // EXTHTTP headers
            elseif (strpos($line, '#EXTHTTP:') === 0 && $current) {
                $this->parseHttp($line, $current);
            }
            // URL line
            elseif ($current && !str_starts_with($line, '#')) {
                $current['url'] = trim($line);
                $channels[] = $current;
                $current = null;
            }
        }
        
        // Process channels for IDs
        $processed_channels = $this->processChannelList($channels);
        
        return [
            'channels' => $processed_channels,
            'total_channels' => count($processed_channels),
            'groups' => $groups,
            'source_file' => $source_filename
        ];
    }
    
    private function parseExtinf($line) {
        $channel = [
            'name' => 'Unknown Channel',
            'logo' => '',
            'group' => 'Uncategorized',  // Default group
            'tvg_id' => '',
            'tvg_name' => '',
            'headers' => []
        ];
        
        // Extract name (after last comma)
        $last_comma = strrpos($line, ',');
        if ($last_comma !== false) {
            $channel['name'] = trim(substr($line, $last_comma + 1));
            $attrs = substr($line, 8, $last_comma - 8);
        } else {
            $channel['name'] = 'Unknown';
            $attrs = substr($line, 8);
        }
        
        // DEBUG: Show what we're parsing
        // echo "Parsing: " . substr($line, 0, 100) . "\n";
        
        // Extract attributes - MULTIPLE METHODS for compatibility
        
        // Method 1: Standard quotes group-title="value"
        if (preg_match('/group-title="([^"]+)"/', $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        }
        // Method 2: Single quotes group-title='value'
        elseif (preg_match("/group-title='([^']+)'/", $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        }
        // Method 3: No quotes group-title=value
        elseif (preg_match('/group-title=([^ ,]+)/', $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        }
        // Method 4: Extract from brackets in name
        elseif (preg_match('/\[([^\]]+)\]/', $channel['name'], $match)) {
            $channel['group'] = trim($match[1]);
            // Remove group from name
            $channel['name'] = trim(str_replace('[' . $match[1] . ']', '', $channel['name']));
        }
        // Method 5: Extract (group) from name
        elseif (preg_match('/\(([^)]+)\)/', $channel['name'], $match)) {
            $channel['group'] = trim($match[1]);
        }
        
        // Extract logo
        if (preg_match('/tvg-logo="([^"]+)"/', $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        }
        elseif (preg_match("/tvg-logo='([^']+)'/", $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        }
        elseif (preg_match('/tvg-logo=([^ ,]+)/', $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        }
        
        // Extract tvg-id
        if (preg_match('/tvg-id="([^"]+)"/', $attrs, $match)) {
            $channel['tvg_id'] = trim($match[1]);
        }
        
        // Extract tvg-name
        if (preg_match('/tvg-name="([^"]+)"/', $attrs, $match)) {
            $channel['tvg_name'] = trim($match[1]);
        }
        
        // Clean up group name
        $channel['group'] = $this->cleanGroupName($channel['group']);
        
        return $channel;
    }
    
    private function cleanGroupName($group) {
        if (empty($group) || $group === 'Uncategorized') {
            return 'Uncategorized';
        }
        
        $group = trim($group);
        
        // Remove common prefixes
        $group = preg_replace('/^\[/', '', $group);
        $group = preg_replace('/\]$/', '', $group);
        $group = preg_replace('/^\(/', '', $group);
        $group = preg_replace('/\)$/', '', $group);
        
        // Capitalize first letter of each word
        $group = ucwords(strtolower($group));
        
        return $group;
    }
    
    private function parseVlcOpt($line, &$channel) {
        $opt = substr($line, 11);
        
        if (strpos($opt, 'http-user-agent=') === 0) {
            $channel['headers']['User-Agent'] = substr($opt, 16);
        }
        elseif (strpos($opt, 'http-referrer=') === 0) {
            $channel['headers']['Referer'] = substr($opt, 14);
        }
        elseif (strpos($opt, 'http-origin=') === 0) {
            $channel['headers']['Origin'] = substr($opt, 12);
        }
    }
    
    private function parseHttp($line, &$channel) {
        $json_str = substr($line, 9);
        
        try {
            $data = @json_decode($json_str, true);
            if ($data && is_array($data)) {
                foreach ($data as $key => $value) {
                    if (is_string($value)) {
                        $channel['headers'][$key] = $value;
                    }
                }
            }
        } catch (Exception $e) {
            // Ignore JSON errors
        }
    }
    
    private function processChannelList($channels) {
        $processed = [];
        
        foreach ($channels as $index => $channel) {
            // Generate ID
            $channel['id'] = $this->generateId($channel) . '_' . ($index + 1);
            
            // Ensure all fields exist
            $channel['logo'] = $channel['logo'] ?? '';
            $channel['group'] = $channel['group'] ?? 'Uncategorized';
            $channel['tvg_id'] = $channel['tvg_id'] ?? '';
            $channel['tvg_name'] = $channel['tvg_name'] ?? $channel['name'];
            $channel['headers'] = $channel['headers'] ?? [];
            
            $processed[] = $channel;
        }
        
        return $processed;
    }
    
    public function processAllChannels($all_channels) {
        if (empty($all_channels)) {
            return [
                'channels' => [],
                'total_channels' => 0,
                'unique_channels' => 0,
                'groups' => [],
                'duplicates' => [],
                'duplicate_count' => 0
            ];
        }
        
        // Group by normalized name
        $channels_by_name = [];
        
        foreach ($all_channels as $channel) {
            $normalized = $this->normalizeName($channel['name']);
            
            if (!isset($channels_by_name[$normalized])) {
                $channels_by_name[$normalized] = [];
            }
            
            $channels_by_name[$normalized][] = $channel;
        }
        
        // Process for duplicates and server numbers
        $processed_channels = [];
        $duplicates = [];
        $groups = [];
        
        foreach ($channels_by_name as $normalized_name => $channel_group) {
            $server_count = count($channel_group);
            
            // Track as duplicate if multiple servers
            if ($server_count > 1) {
                $sample_channel = $channel_group[0];
                $duplicates[$normalized_name] = [
                    'display_name' => $sample_channel['name'],
                    'server_count' => $server_count,
                    'servers' => array_unique(array_column($channel_group, 'source_file')),
                    'sample_channel_id' => $this->generateId($sample_channel)
                ];
            }
            
            // Add each channel with server number
            foreach ($channel_group as $index => $channel) {
                $channel['server_number'] = $index + 1;
                $channel['total_servers'] = $server_count;
                $channel['normalized_name'] = $normalized_name;
                $channel['id'] = $this->generateId($channel) . '_' . ($index + 1);
                
                // Track groups
                $group = $channel['group'];
                if (!isset($groups[$group])) {
                    $groups[$group] = 0;
                }
                $groups[$group]++;
                
                $processed_channels[] = $channel;
            }
        }
        
        // Sort by name for consistency
        usort($processed_channels, function($a, $b) {
            return strcmp($a['name'], $b['name']);
        });
        
        return [
            'channels' => $processed_channels,
            'total_channels' => count($processed_channels),
            'unique_channels' => count($channels_by_name),
            'groups' => $groups,
            'duplicates' => $duplicates,
            'duplicate_count' => count($duplicates)
        ];
    }
    
    private function generateId($channel) {
        // Create a consistent ID from name and URL
        $name_part = strtolower(preg_replace('/[^a-z0-9]/', '_', $channel['name']));
        $name_part = preg_replace('/_+/', '_', $name_part);
        $name_part = trim($name_part, '_');
        $name_part = substr($name_part, 0, 30);
        
        $url_part = substr(md5($channel['url'] ?? uniqid()), 0, 8);
        
        return $name_part . '_' . $url_part;
    }
    
    private function normalizeName($name) {
        $name = strtolower(trim($name));
        
        // Remove common prefixes/suffixes
        $name = preg_replace('/\[.*?\]/', '', $name);
        $name = preg_replace('/\s*(hd|fhd|uhd|4k|sd|tv|channel|live|stream|plus|extra|pro|max)$/i', '', $name);
        $name = preg_replace('/[^a-z0-9\s]/', ' ', $name);
        $name = preg_replace('/\s+/', ' ', $name);
        
        return trim($name);
    }
}
?>
