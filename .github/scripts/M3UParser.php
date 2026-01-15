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
        
        foreach ($lines as $line) {
            $line = trim($line);
            if (empty($line)) continue;
            
            // EXTINF line - start new channel
            if (strpos($line, '#EXTINF:') === 0) {
                // Save previous channel if exists
                if ($current_channel) {
                    $channels[] = $current_channel;
                }
                
                // Parse new channel
                $current_channel = $this->parseExtinf($line);
                $current_channel['source_file'] = $source_filename;
                $current_channel['headers'] = [];
            }
            // EXTVLCOPT headers
            elseif (strpos($line, '#EXTVLCOPT:') === 0 && $current_channel) {
                $headers = $this->parseVlcOpt($line);
                $current_channel['headers'] = array_merge($current_channel['headers'], $headers);
            }
            // EXTHTTP headers
            elseif (strpos($line, '#EXTHTTP:') === 0 && $current_channel) {
                $headers = $this->parseHttp($line);
                $current_channel['headers'] = array_merge($current_channel['headers'], $headers);
            }
            // URL line
            elseif ($current_channel && !str_starts_with($line, '#')) {
                $current_channel['url'] = trim($line);
                $channels[] = $current_channel;
                $current_channel = null;
            }
        }
        
        // Add last channel if exists
        if ($current_channel) {
            $channels[] = $current_channel;
        }
        
        return $channels;
    }
    
    private function parseExtinf($line) {
        // Find the last comma (channel name is after it)
        $last_comma = strrpos($line, ',');
        if ($last_comma === false) {
            return [
                'name' => 'Unknown',
                'original_name' => 'Unknown',
                'logo' => '',
                'group' => 'Uncategorized',
                'tvg_id' => '',
                'tvg_name' => '',
                'headers' => []
            ];
        }
        
        $raw_name = trim(substr($line, $last_comma + 1));
        $attrs = substr($line, 8, $last_comma - 8);
        
        return [
            'name' => $this->cleanChannelName($raw_name),
            'original_name' => $raw_name,
            'logo' => $this->extractAttribute($attrs, 'tvg-logo'),
            'group' => $this->cleanGroupName($this->extractAttribute($attrs, 'group-title')),
            'tvg_id' => $this->extractAttribute($attrs, 'tvg-id'),
            'tvg_name' => $this->extractAttribute($attrs, 'tvg-name'),
            'headers' => []
        ];
    }
    
    private function extractAttribute($attrs, $attribute_name) {
        $patterns = [
            '/\b' . $attribute_name . '\s*=\s*"([^"]*)"/i',
            "/\b" . $attribute_name . "\s*=\s*'([^']*)'/i",
            '/\b' . $attribute_name . '\s*=\s*([^ ,]+)/i',
        ];
        
        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $attrs, $match)) {
                return trim($match[1]);
            }
        }
        
        return '';
    }
    
    private function cleanChannelName($name) {
        // Remove [BD], (BD), [LIVE], etc.
        $name = preg_replace('/^\[BD\]\s*/i', '', $name);
        $name = preg_replace('/^\(BD\)\s*/i', '', $name);
        $name = preg_replace('/^\[LIVE\]\s*/i', '', $name);
        
        // Remove quality suffixes
        $name = preg_replace('/\s*(HD|FHD|4K|UHD|SD|LOW)\s*$/i', '', $name);
        
        // Trim and clean
        $name = trim($name);
        $name = preg_replace('/\s+/', ' ', $name);
        
        return $name;
    }
    
    private function cleanGroupName($group) {
        if (empty($group)) return 'Uncategorized';
        
        $group = trim($group);
        $group = trim($group, '"\'');
        $group = preg_replace('/^\[|\]$/', '', $group);
        $group = ucwords(strtolower($group));
        
        return $group;
    }
    
    private function parseVlcOpt($line) {
        $opt = substr($line, 11); // Remove '#EXTVLCOPT:'
        $headers = [];
        
        // Extract User-Agent
        if (preg_match('/http-user-agent\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $headers['User-Agent'] = $value;
        }
        
        // Extract Referer
        if (preg_match('/http-referer(r)?\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[2], " '\"");
            $headers['Referer'] = $value;
        }
        
        // Extract Origin
        if (preg_match('/http-origin\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $headers['Origin'] = $value;
        }
        
        // Extract Cookie
        if (preg_match('/http-cookie\s*=\s*(.+)/i', $opt, $match)) {
            $value = trim($match[1], " '\"");
            $headers['Cookie'] = $value;
        }
        
        return $headers;
    }
    
    private function parseHttp($line) {
        $json_str = substr($line, 9); // Remove '#EXTHTTP:'
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
            // Ignore errors
        }
        
        return $headers;
    }
    
    public function groupChannelsByDuplicate($channels) {
        $grouped = [];
        
        foreach ($channels as $channel) {
            // Generate a unique key based on cleaned channel name
            $key = $this->generateChannelKey($channel['name']);
            
            // If this is the first time seeing this channel
            if (!isset($grouped[$key])) {
                $grouped[$key] = [
                    'name' => $channel['name'],
                    'logo' => $channel['logo'] ?: $this->getBestLogo($channels, $key),
                    'group' => $channel['group'],
                    'tvg_id' => $channel['tvg_id'],
                    'tvg_name' => $channel['tvg_name'] ?: $channel['name'],
                    'servers' => []
                ];
            }
            
            // Add this as a server
            $server_number = count($grouped[$key]['servers']) + 1;
            
            // Determine quality from original name
            $quality = $this->extractQuality($channel['original_name']);
            
            $grouped[$key]['servers'][] = [
                'url' => $channel['url'],
                'quality' => $quality,
                'priority' => $this->calculatePriority($channel, $quality),
                'headers' => $channel['headers'],
                'server_number' => $server_number
            ];
        }
        
        // Sort servers by priority (highest first)
        foreach ($grouped as &$channel) {
            usort($channel['servers'], function($a, $b) {
                return $b['priority'] - $a['priority'];
            });
            
            // Re-number servers after sorting
            foreach ($channel['servers'] as $index => &$server) {
                $server['priority'] = $index + 1;
                $server['server_number'] = $index + 1;
            }
        }
        
        // Sort channels alphabetically
        ksort($grouped);
        
        return $grouped;
    }
    
    private function generateChannelKey($channel_name) {
        // Convert to lowercase, remove special chars, replace spaces with underscores
        $key = strtolower($channel_name);
        $key = preg_replace('/[^a-z0-9]/', '_', $key);
        $key = preg_replace('/_+/', '_', $key);
        $key = trim($key, '_');
        
        return $key;
    }
    
    private function getBestLogo($channels, $channel_key) {
        // Find the first non-empty logo for this channel
        foreach ($channels as $channel) {
            $key = $this->generateChannelKey($channel['name']);
            if ($key === $channel_key && !empty($channel['logo'])) {
                return $channel['logo'];
            }
        }
        
        return '';
    }
    
    private function extractQuality($original_name) {
        $original_name = strtoupper($original_name);
        
        if (strpos($original_name, '4K') !== false || strpos($original_name, 'UHD') !== false) {
            return '4K';
        }
        if (strpos($original_name, 'FHD') !== false) {
            return 'Full HD';
        }
        if (strpos($original_name, 'HD') !== false) {
            return 'HD';
        }
        if (strpos($original_name, 'SD') !== false) {
            return 'SD';
        }
        
        return 'Unknown';
    }
    
    private function calculatePriority($channel, $quality) {
        $priority = 0;
        
        // Higher priority for better quality
        switch ($quality) {
            case '4K': $priority += 100; break;
            case 'Full HD': $priority += 80; break;
            case 'HD': $priority += 60; break;
            case 'SD': $priority += 40; break;
        }
        
        // Higher priority for HTTPS URLs
        if (strpos($channel['url'], 'https://') === 0) {
            $priority += 20;
        }
        
        // Higher priority for .m3u8 URLs
        if (strpos($channel['url'], '.m3u8') !== false) {
            $priority += 10;
        }
        
        // Higher priority if headers exist (more likely to work)
        if (!empty($channel['headers'])) {
            $priority += 30;
        }
        
        return $priority;
    }
}
?>