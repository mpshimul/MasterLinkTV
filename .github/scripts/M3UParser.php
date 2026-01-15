<?php
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
        $current_channel = null;
        $current_headers = [];
        $got_url = false;
        
        foreach ($lines as $line) {
            $line = trim($line);
            if (empty($line)) continue;
            
            // DEBUG: Uncomment to see parsing
            // echo "Line: " . substr($line, 0, 100) . "...\n";
            
            // EXTINF line - start new channel
            if (strpos($line, '#EXTINF:') === 0) {
                // Save previous channel if exists
                if ($current_channel) {
                    $current_channel['headers'] = $current_headers;
                    $channels[] = $current_channel;
                }
                
                // Start new channel
                $current_channel = $this->parseExtinf($line);
                $current_channel['source_file'] = $source_filename;
                $current_headers = [];
                $got_url = false;
            }
            // URL line
            elseif ($current_channel && !str_starts_with($line, '#')) {
                $current_channel['url'] = trim($line);
                $current_channel['quality'] = $this->extractQuality($current_channel['name']);
                $got_url = true; // Mark that we got the URL, headers come next
            }
            // EXTVLCOPT headers - only capture if we already have URL
            elseif ($got_url && strpos($line, '#EXTVLCOPT:') === 0) {
                $headers = $this->parseVlcOpt($line);
                $current_headers = array_merge($current_headers, $headers);
            }
            // EXTHTTP headers - only capture if we already have URL
            elseif ($got_url && strpos($line, '#EXTHTTP:') === 0) {
                $headers = $this->parseHttp($line);
                $current_headers = array_merge($current_headers, $headers);
            }
        }
        
        // Don't forget the last channel
        if ($current_channel) {
            $current_channel['headers'] = $current_headers;
            $channels[] = $current_channel;
        }
        
        return $channels;
    }
    
    private function parseExtinf($line) {
        $channel = [
            'name' => '',
            'logo' => '',
            'group' => 'Uncategorized',
            'tvg_id' => '',
            'tvg_name' => '',
            'headers' => []
        ];
        
        // Find the last comma
        $last_comma = strrpos($line, ',');
        if ($last_comma === false) {
            $channel['name'] = 'Unknown';
            return $channel;
        }
        
        // Extract raw name and attributes
        $raw_name = trim(substr($line, $last_comma + 1));
        $attrs = substr($line, 8, $last_comma - 8);
        
        // Store original name
        $channel['original_name'] = $raw_name;
        
        // Clean the channel name
        $channel['name'] = $this->cleanChannelName($raw_name);
        
        // If name is still empty after cleaning, use original
        if (empty($channel['name'])) {
            $channel['name'] = $raw_name;
        }
        
        // Extract group-title (handle quotes)
        if (preg_match('/group-title\s*=\s*"([^"]*)"/i', $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        } elseif (preg_match("/group-title\s*=\s*'([^']*)'/i", $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        } elseif (preg_match('/group-title\s*=\s*([^ ,]+)/i', $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        }
        
        // Extract logo
        if (preg_match('/tvg-logo\s*=\s*"([^"]*)"/i', $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        } elseif (preg_match("/tvg-logo\s*=\s*'([^']*)'/i", $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        } elseif (preg_match('/tvg-logo\s*=\s*([^ ,\s]+)/i', $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        }
        
        // Clean group name
        $channel['group'] = $this->cleanGroupName($channel['group']);
        
        return $channel;
    }
    
    private function cleanChannelName($name) {
        if (empty($name)) return '';
        
        // Remove [BD], (BD), etc.
        $name = preg_replace('/^\[BD\]\s*/i', '', $name);
        $name = preg_replace('/^\(BD\)\s*/i', '', $name);
        $name = preg_replace('/^\[LIVE\]\s*/i', '', $name);
        $name = preg_replace('/^\[.*?\]\s*/', '', $name);
        
        // Remove quality suffixes
        $name = preg_replace('/\s*(HD|FHD|4K|UHD|SD|LOW|HQ)\s*$/i', '', $name);
        
        // Trim and clean
        $name = trim($name);
        $name = preg_replace('/\s+/', ' ', $name);
        
        return $name;
    }
    
    private function extractQuality($name) {
        $name_upper = strtoupper($name);
        
        if (strpos($name_upper, '4K') !== false || strpos($name_upper, 'UHD') !== false) {
            return '4K';
        } elseif (strpos($name_upper, 'FULL HD') !== false || strpos($name_upper, 'FHD') !== false) {
            return 'Full HD';
        } elseif (strpos($name_upper, 'HD') !== false) {
            return 'HD';
        } elseif (strpos($name_upper, 'SD') !== false) {
            return 'SD';
        }
        
        return 'Unknown';
    }
    
    private function parseVlcOpt($line) {
        $opt = substr($line, 11); // Remove '#EXTVLCOPT:'
        $opt = trim($opt);
        $headers = [];
        
        // http-user-agent
        if (preg_match('/http-user-agent\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $headers['User-Agent'] = $value;
        }
        // http-referrer (note: some use Referer, some use Referrer)
        elseif (preg_match('/http-referrer\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $headers['Referer'] = $value;
        }
        // http-referer
        elseif (preg_match('/http-referer\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $headers['Referer'] = $value;
        }
        // http-origin
        elseif (preg_match('/http-origin\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $headers['Origin'] = $value;
        }
        // http-cookie
        elseif (preg_match('/http-cookie\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $headers['Cookie'] = $value;
        }
        
        return $headers;
    }
    
    private function parseHttp($line) {
        $json_str = substr($line, 9); // Remove '#EXTHTTP:'
        $json_str = trim($json_str);
        $headers = [];
        
        try {
            $data = @json_decode($json_str, true);
            if (is_array($data)) {
                foreach ($data as $key => $value) {
                    if (is_string($value)) {
                        $headers[$key] = $value;
                    }
                }
            }
        } catch (Exception $e) {
            // Ignore JSON errors
        }
        
        return $headers;
    }
    
    public function groupChannelsByDuplicate($channels) {
        $grouped = [];
        
        foreach ($channels as $channel) {
            // Skip channels with empty names
            if (empty(trim($channel['name'] ?? ''))) {
                continue;
            }
            
            // Create key based on normalized name and group
            $key = $this->createChannelKey($channel);
            
            if (!isset($grouped[$key])) {
                $grouped[$key] = [
                    'id' => $this->generateChannelId($channel['name']),
                    'name' => $channel['name'],
                    'logo' => $channel['logo'] ?? '',
                    'group' => $channel['group'] ?? 'Uncategorized',
                    'quality' => $channel['quality'] ?? 'Unknown',
                    'servers' => []
                ];
            }
            
            // Add server
            $server_count = count($grouped[$key]['servers']) + 1;
            $priority = $this->calculatePriority($channel, $server_count);
            
            $grouped[$key]['servers'][] = [
                'url' => $channel['url'] ?? '',
                'quality' => $channel['quality'] ?? 'Unknown',
                'priority' => $priority,
                'headers' => $channel['headers'] ?? [],
                'source_file' => $channel['source_file'] ?? 'unknown',
                'server_number' => $server_count
            ];
        }
        
        // Sort servers by priority (highest first)
        foreach ($grouped as &$channel) {
            usort($channel['servers'], function($a, $b) {
                return ($b['priority'] ?? 1) - ($a['priority'] ?? 1);
            });
            
            // Update server numbers
            foreach ($channel['servers'] as $index => &$server) {
                $server['priority'] = $index + 1;
                $server['server_number'] = $index + 1;
            }
        }
        
        return $grouped;
    }
    
    private function createChannelKey($channel) {
        $name = strtolower($channel['name']);
        $group = strtolower($channel['group'] ?? '');
        
        // Normalize name
        $name = preg_replace('/[^a-z0-9]/', '_', $name);
        $name = preg_replace('/_+/', '_', $name);
        $name = trim($name, '_');
        
        // Normalize group
        $group = preg_replace('/[^a-z0-9]/', '_', $group);
        $group = preg_replace('/_+/', '_', $group);
        $group = trim($group, '_');
        
        return $name . '_' . $group;
    }
    
    private function generateChannelId($name) {
        $id = strtolower($name);
        $id = preg_replace('/[^a-z0-9]/', '_', $id);
        $id = preg_replace('/_+/', '_', $id);
        $id = trim($id, '_');
        $id = substr($id, 0, 50);
        
        if (empty($id)) {
            $id = 'channel_' . substr(md5($name), 0, 8);
        }
        
        return $id;
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
        }
        
        // Higher priority for HTTPS
        if (strpos($channel['url'] ?? '', 'https://') === 0) {
            $priority += 20;
        }
        
        // Higher priority for .m3u8
        if (strpos($channel['url'] ?? '', '.m3u8') !== false) {
            $priority += 10;
        }
        
        // Higher priority if headers exist
        if (!empty($channel['headers'])) {
            $priority += 30;
        }
        
        return $priority;
    }
    
    private function cleanGroupName($group) {
        if (empty($group)) return 'Uncategorized';
        
        $group = trim($group);
        $group = trim($group, '"\'');
        
        // Remove brackets
        $group = preg_replace('/^\[|\]$/', '', $group);
        
        // Remove special characters
        $group = preg_replace('/[^\p{L}\p{N}\s\-]/u', ' ', $group);
        $group = preg_replace('/\s+/', ' ', $group);
        $group = trim($group);
        
        // Capitalize properly
        $group = ucwords(strtolower($group));
        
        return $group;
    }
}
?>