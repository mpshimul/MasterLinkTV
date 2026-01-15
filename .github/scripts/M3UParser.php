<?php
// M3UParser.php - Enhanced parser for server grouping

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
    
    public function groupChannelsByDuplicate($channels) {
        $grouped = [];
        $channel_map = [];
        
        foreach ($channels as $channel) {
            // Create a unique key based on normalized name
            $key = $this->createChannelKey($channel);
            
            if (!isset($grouped[$key])) {
                // First entry for this channel
                $grouped[$key] = [
                    'id' => $this->generateChannelId($channel['name']),
                    'name' => $this->cleanChannelName($channel['name']),
                    'logo' => $channel['logo'] ?? '',
                    'group' => $channel['group'] ?? 'Uncategorized',
                    'tvg_id' => $channel['tvg_id'] ?? '',
                    'tvg_name' => $channel['tvg_name'] ?? $this->cleanChannelName($channel['name']),
                    'quality' => $channel['quality'] ?? 'Unknown',
                    'servers' => []
                ];
            }
            
            // Add server with headers and priority
            $server_count = count($grouped[$key]['servers']) + 1;
            $priority = $this->calculatePriority($channel, $server_count);
            
            $grouped[$key]['servers'][] = [
                'id' => $grouped[$key]['id'] . '_server_' . $server_count,
                'url' => $channel['url'],
                'quality' => $channel['quality'] ?? 'Unknown',
                'priority' => $priority,
                'headers' => $channel['headers'] ?? [],
                'source_file' => $channel['source_file'] ?? 'unknown',
                'original_name' => $channel['name'] ?? '',
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
        // Normalize the name for grouping
        $name = $this->normalizeChannelName($channel['name']);
        $group = $channel['group'] ?? 'Uncategorized';
        
        // Create key from normalized name and group
        return md5(strtolower($name . '_' . $group));
    }
    
    private function normalizeChannelName($name) {
        $name = trim($name);
        
        // Remove quality indicators
        $name = preg_replace('/\s*(4K|UHD|FHD|HD|SD|LOW|HQ)\s*/i', ' ', $name);
        
        // Remove common prefixes/suffixes
        $name = preg_replace('/\s*\[.*?\]\s*/', ' ', $name);
        $name = preg_replace('/\s*\(.*?\)\s*/', ' ', $name);
        
        // Remove special characters but keep spaces
        $name = preg_replace('/[^\p{L}\p{N}\s]/u', ' ', $name);
        
        // Convert to lowercase and trim
        $name = strtolower(trim($name));
        $name = preg_replace('/\s+/', ' ', $name);
        
        return $name;
    }
    
    private function cleanChannelName($name) {
        $name = trim($name);
        
        // Remove server indicators
        $name = preg_replace('/\s*\[server\s*\d+\]/i', '', $name);
        $name = preg_replace('/\s*\(server\s*\d+\)/i', '', $name);
        
        // Clean up extra spaces
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
    
    // Keep existing parseExtinf, parseVlcOpt, parseHttp, cleanGroupName methods
    private function parseExtinf($line) {
        $channel = [
            'name' => 'Unknown Channel',
            'logo' => '',
            'group' => 'Uncategorized',
            'tvg_id' => '',
            'tvg_name' => '',
            'headers' => []
        ];
        
        $last_comma = strrpos($line, ',');
        if ($last_comma !== false) {
            $channel['name'] = trim(substr($line, $last_comma + 1));
            $attrs = substr($line, 8, $last_comma - 8);
        } else {
            $channel['name'] = 'Unknown';
            $attrs = substr($line, 8);
        }
        
        // Extract group-title
        if (preg_match('/group-title\s*=\s*"([^"]*)"/i', $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        } elseif (preg_match("/group-title\s*=\s*'([^']*)'/i", $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        } elseif (preg_match('/group-title\s*=\s*([^ ,\s]+)/i', $attrs, $match)) {
            $channel['group'] = trim($match[1]);
        }
        
        // Extract logo
        if (preg_match('/tvg-logo\s*=\s*"([^"]*)"/i', $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        } elseif (preg_match("/tvg-logo\s*=\s*'([^']*)'/i", $attrs, $match)) {
            $channel['logo'] = trim($match[1]);
        }
        
        // Clean group name
        $channel['group'] = $this->cleanGroupName($channel['group']);
        
        return $channel;
    }
    
    private function cleanGroupName($group) {
        if (empty($group) || trim($group) === '') {
            return 'Uncategorized';
        }
        
        $group = trim($group);
        $group = preg_replace('/^[\[\{\(](.+)[\]\}\)]$/', '$1', $group);
        $group = preg_replace('/[^\p{L}\p{N}\s\-]/u', ' ', $group);
        $group = preg_replace('/\s+/', ' ', $group);
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
        elseif (strpos($opt, 'http-cookie=') === 0) {
            $channel['headers']['Cookie'] = substr($opt, 12);
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
}
?>