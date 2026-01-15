<?php
// M3UParser.php - Enhanced parser with better name cleaning and group extraction

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
        $current = null;
        
        foreach ($lines as $line) {
            $line = trim($line);
            if (empty($line)) continue;
            
            // EXTINF line
            if (strpos($line, '#EXTINF:') === 0) {
                $current = $this->parseExtinf($line);
                $current['source_file'] = $source_filename;
                $current['headers'] = []; // Initialize headers array
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
                
                // Try to extract quality from name
                $current['quality'] = $this->extractQuality($current['name']);
                
                $channels[] = $current;
                $current = null;
            }
        }
        
        return $channels;
    }
    
    private function parseExtinf($line) {
        $channel = [
            'name' => 'Unknown Channel',
            'logo' => '',
            'group' => 'Uncategorized',
            'tvg_id' => '',
            'tvg_name' => '',
            'headers' => [] // Initialize headers
        ];
        
        $last_comma = strrpos($line, ',');
        if ($last_comma !== false) {
            $raw_name = trim(substr($line, $last_comma + 1));
            $attrs = substr($line, 8, $last_comma - 8);
            
            // Clean the channel name
            $channel['name'] = $this->cleanChannelName($raw_name);
            
            // Extract original name before cleaning for debugging
            $channel['original_name'] = $raw_name;
        } else {
            $channel['name'] = 'Unknown';
            $channel['original_name'] = 'Unknown';
            $attrs = substr($line, 8);
        }
        
        // DEBUG: Uncomment to see what we're parsing
        // echo "Raw name: '$raw_name' -> Cleaned: '" . $channel['name'] . "'\n";
        // echo "Attrs: $attrs\n";
        
        // Extract group-title - handle both quoted and unquoted
        $group_found = false;
        
        // Pattern 1: group-title="value" (with quotes)
        if (preg_match('/group-title\s*=\s*"([^"]*)"/i', $attrs, $match)) {
            $channel['group'] = trim($match[1]);
            $group_found = true;
        }
        // Pattern 2: group-title='value' (with single quotes)
        elseif (preg_match("/group-title\s*=\s*'([^']*)'/i", $attrs, $match)) {
            $channel['group'] = trim($match[1]);
            $group_found = true;
        }
        // Pattern 3: group-title=value (no quotes)
        elseif (preg_match('/group-title\s*=\s*([^ ,]+)/i', $attrs, $match)) {
            $channel['group'] = trim($match[1]);
            $group_found = true;
        }
        
        // If group was found in attributes, clean it
        if ($group_found) {
            $channel['group'] = $this->cleanGroupName($channel['group']);
        } else {
            // Try to extract group from the original name
            $channel['group'] = $this->extractGroupFromName($channel['original_name']);
        }
        
        // Extract logo
        if (preg_match('/tvg-logo\s*=\s*"([^"]*)"/i', $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        } elseif (preg_match("/tvg-logo\s*=\s*'([^']*)'/i", $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        } elseif (preg_match('/tvg-logo\s*=\s*([^ ,\s]+)/i', $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        }
        
        // Extract tvg-id
        if (preg_match('/tvg-id\s*=\s*"([^"]*)"/i', $attrs, $match)) {
            $channel['tvg_id'] = trim($match[1]);
        }
        
        // Extract tvg-name
        if (preg_match('/tvg-name\s*=\s*"([^"]*)"/i', $attrs, $match)) {
            $channel['tvg_name'] = trim($match[1]);
        }
        
        // If tvg_name is empty, use cleaned name
        if (empty($channel['tvg_name'])) {
            $channel['tvg_name'] = $channel['name'];
        }
        
        return $channel;
    }
    
    private function cleanChannelName($name) {
        // Remove common prefixes like [BD], (BD), [LIVE], etc.
        $patterns = [
            '/^\[BD\]\s*/i',          // [BD]
            '/^\(BD\)\s*/i',          // (BD)
            '/^\[LIVE\]\s*/i',        // [LIVE]
            '/^\[.*?\]\s*/',          // Any [something]
            '/^\(.*?\)\s*/',          // Any (something)
            '/^\s*-\s*/',             // Leading dash
            '/\s*\[.*?\]\s*$/i',      // Trailing [something]
            '/\s*\(.*?\)\s*$/i',      // Trailing (something)
            '/\s*HD\s*$/i',           // Trailing HD
            '/\s*FHD\s*$/i',          // Trailing FHD
            '/\s*4K\s*$/i',           // Trailing 4K
            '/\s*SD\s*$/i',           // Trailing SD
        ];
        
        $cleaned = $name;
        foreach ($patterns as $pattern) {
            $cleaned = preg_replace($pattern, '', $cleaned);
        }
        
        // Trim and clean up extra spaces
        $cleaned = trim($cleaned);
        $cleaned = preg_replace('/\s+/', ' ', $cleaned);
        
        // If after cleaning it's empty, use original
        if (empty($cleaned)) {
            return $name;
        }
        
        return $cleaned;
    }
    
    private function extractGroupFromName($name) {
        // Try to extract group from name patterns
        $patterns = [
            '/^\[([^\]]+)\]\s*([^\[\]]+)$/',  // [group] channel
            '/^([^\[\]]+)\s*\[([^\]]+)\]$/',  // channel [group]
            '/^\(([^\)]+)\)\s*([^\(\)]+)$/',  // (group) channel
            '/^([^\(\)]+)\s*\(([^\)]+)\)$/',  // channel (group)
        ];
        
        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $name, $match)) {
                // Check which part is likely the group
                if (strlen($match[1]) < 20 && strlen($match[2]) > strlen($match[1])) {
                    // match[1] is likely the group (shorter)
                    return $this->cleanGroupName($match[1]);
                } elseif (strlen($match[2]) < 20 && strlen($match[1]) > strlen($match[2])) {
                    // match[2] is likely the group (shorter)
                    return $this->cleanGroupName($match[2]);
                }
            }
        }
        
        return 'Uncategorized';
    }
    
    private function extractQuality($name) {
        $name_lower = strtolower($name);
        
        if (strpos($name_lower, '4k') !== false || strpos($name_lower, 'uhd') !== false) {
            return '4K';
        } elseif (strpos($name_lower, 'full hd') !== false || strpos($name_lower, 'fhd') !== false) {
            return 'Full HD';
        } elseif (strpos($name_lower, 'hd') !== false) {
            return 'HD';
        } elseif (strpos($name_lower, 'sd') !== false) {
            return 'SD';
        } elseif (strpos($name_lower, 'low') !== false) {
            return 'Low';
        }
        
        return 'Unknown';
    }
    
    private function parseVlcOpt($line, &$channel) {
        $opt = substr($line, 11); // Remove '#EXTVLCOPT:'
        $opt = trim($opt);
        
        // http-user-agent
        if (preg_match('/http-user-agent\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $channel['headers']['User-Agent'] = $value;
        }
        // http-referrer (note: some use Referer, some use Referrer)
        elseif (preg_match('/http-referrer\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $channel['headers']['Referer'] = $value;
        }
        // http-referer (alternative spelling)
        elseif (preg_match('/http-referer\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $channel['headers']['Referer'] = $value;
        }
        // http-origin
        elseif (preg_match('/http-origin\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $channel['headers']['Origin'] = $value;
        }
        // http-cookie
        elseif (preg_match('/http-cookie\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $channel['headers']['Cookie'] = $value;
        }
        // Custom headers
        elseif (preg_match('/http-([a-zA-Z0-9\-]+)\s*=\s*(.+)/i', $opt, $match)) {
            $header_name = ucwords(strtolower(str_replace('-', ' ', $match[1])));
            $header_name = str_replace(' ', '-', $header_name);
            $value = trim($match[2], " '\"");
            $channel['headers'][$header_name] = $value;
        }
    }
    
    private function parseHttp($line, &$channel) {
        $json_str = substr($line, 9); // Remove '#EXTHTTP:'
        $json_str = trim($json_str);
        
        try {
            $data = @json_decode($json_str, true);
            if ($data && is_array($data)) {
                foreach ($data as $key => $value) {
                    if (is_string($value)) {
                        $channel['headers'][$key] = $value;
                    } elseif (is_array($value)) {
                        foreach ($value as $sub_key => $sub_value) {
                            if (is_string($sub_value)) {
                                $full_key = $key . '-' . $sub_key;
                                $channel['headers'][$full_key] = $sub_value;
                            }
                        }
                    }
                }
            }
        } catch (Exception $e) {
            // Ignore JSON errors
        }
    }
    
    public function groupChannelsByDuplicate($channels) {
        $grouped = [];
        
        foreach ($channels as $channel) {
            // Create a unique key based on CLEANED normalized name and group
            $key = $this->createChannelKey($channel);
            
            if (!isset($grouped[$key])) {
                // First entry for this channel
                $grouped[$key] = [
                    'id' => $this->generateChannelId($channel['name']),
                    'name' => $channel['name'], // Already cleaned in parseExtinf
                    'original_name' => $channel['original_name'] ?? $channel['name'],
                    'logo' => $channel['logo'] ?? '',
                    'group' => $channel['group'] ?? 'Uncategorized',
                    'tvg_id' => $channel['tvg_id'] ?? '',
                    'tvg_name' => $channel['tvg_name'] ?? $channel['name'],
                    'quality' => $channel['quality'] ?? 'Unknown',
                    'servers' => []
                ];
            }
            
            // Add server with headers and priority
            $server_count = count($grouped[$key]['servers']) + 1;
            $priority = $this->calculatePriority($channel, $server_count);
            
            // Ensure headers array exists
            $headers = $channel['headers'] ?? [];
            
            $grouped[$key]['servers'][] = [
                'id' => $grouped[$key]['id'] . '_server_' . $server_count,
                'url' => $channel['url'],
                'quality' => $channel['quality'] ?? 'Unknown',
                'priority' => $priority,
                'headers' => $headers,
                'source_file' => $channel['source_file'] ?? 'unknown',
                'server_number' => $server_count
            ];
        }
        
        // Sort servers by priority (highest first)
        foreach ($grouped as &$channel) {
            usort($channel['servers'], function($a, $b) {
                return $b['priority'] - $a['priority'];
            });
            
            // Update server numbers after sorting
            foreach ($channel['servers'] as $index => &$server) {
                $server['priority'] = $index + 1;
                $server['server_number'] = $index + 1;
            }
            
            // Determine overall quality based on best server
            $channel['quality'] = $this->getBestQuality($channel['servers']);
        }
        
        // Sort channels by name
        uksort($grouped, function($a, $b) use ($grouped) {
            return strcmp($grouped[$a]['name'], $grouped[$b]['name']);
        });
        
        return $grouped;
    }
    
    private function createChannelKey($channel) {
        // Use CLEANED name and group for grouping
        $name = $this->normalizeChannelName($channel['name']);
        $group = $channel['group'] ?? 'Uncategorized';
        
        // Create key from normalized CLEANED name and group
        return md5(strtolower($name . '_' . $group));
    }
    
    private function normalizeChannelName($name) {
        $name = trim($name);
        
        // Remove any remaining brackets/parentheses
        $name = preg_replace('/\s*\[.*?\]\s*/', ' ', $name);
        $name = preg_replace('/\s*\(.*?\)\s*/', ' ', $name);
        
        // Remove quality indicators
        $name = preg_replace('/\s*(4K|UHD|FHD|HD|SD|LOW|HQ)\s*/i', ' ', $name);
        
        // Remove special characters but keep spaces
        $name = preg_replace('/[^\p{L}\p{N}\s]/u', ' ', $name);
        
        // Convert to lowercase and trim
        $name = strtolower(trim($name));
        $name = preg_replace('/\s+/', ' ', $name);
        
        return $name;
    }
    
    private function generateChannelId($name) {
        $name = $this->normalizeChannelName($name);
        $name = preg_replace('/[^a-z0-9]/', '_', $name);
        $name = preg_replace('/_+/', '_', $name);
        $name = trim($name, '_');
        $name = substr($name, 0, 50);
        
        return $name;
    }
    
    private function calculatePriority($channel, $default_priority) {
        $priority = $default_priority;
        
        // Higher priority for better quality
        $quality = strtolower($channel['quality'] ?? 'unknown');
        switch ($quality) {
            case '4k': $priority += 100; break;
            case 'full hd': $priority += 80; break;
            case 'hd': $priority += 60; break;
            case 'sd': $priority += 40; break;
            case 'low': $priority += 20; break;
        }
        
        // Higher priority for URLs with HTTPS
        if (strpos($channel['url'] ?? '', 'https://') === 0) {
            $priority += 10;
        }
        
        // Higher priority for .m3u8 files
        if (strpos($channel['url'] ?? '', '.m3u8') !== false) {
            $priority += 5;
        }
        
        // Higher priority for channels with proper headers (likely working)
        if (!empty($channel['headers'])) {
            $priority += 15;
        }
        
        return $priority;
    }
    
    private function getBestQuality($servers) {
        $qualities = ['4K' => 100, 'Full HD' => 80, 'HD' => 60, 'SD' => 40, 'Low' => 20, 'Unknown' => 0];
        $best_quality = 'Unknown';
        $best_score = 0;
        
        foreach ($servers as $server) {
            $quality = $server['quality'] ?? 'Unknown';
            $score = $qualities[$quality] ?? 0;
            
            if ($score > $best_score) {
                $best_score = $score;
                $best_quality = $quality;
            }
        }
        
        return $best_quality;
    }
    
    private function cleanGroupName($group) {
        if (empty($group) || trim($group) === '') {
            return 'Uncategorized';
        }
        
        $group = trim($group);
        
        // Remove quotes if present
        $group = trim($group, '"\'');
        
        // Remove brackets/parentheses
        $group = preg_replace('/^[\[\{\(](.+)[\]\}\)]$/', '$1', $group);
        
        // Clean up special characters
        $group = preg_replace('/[^\p{L}\p{N}\s\-]/u', ' ', $group);
        $group = preg_replace('/\s+/', ' ', $group);
        $group = ucwords(strtolower($group));
        
        return $group;
    }
}
?>