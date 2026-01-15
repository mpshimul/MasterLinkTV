<?php
// .github/scripts/M3UParser.php
// Advanced M3U parser with duplicate detection

class M3UParser {
    
    public function processFile($filename) {
        if (!file_exists($filename)) {
            throw new Exception("File not found: $filename");
        }
        
        $content = file_get_contents($filename);
        return $this->parse($content);
    }
    
    public function parse($m3uContent) {
        $lines = explode("\n", $m3uContent);
        $channels = [];
        $groups = [];
        $channelMap = []; // For duplicate detection
        $current = null;
        
        foreach ($lines as $line) {
            $line = trim($line);
            if (empty($line)) continue;
            
            // EXTINF line
            if (strpos($line, '#EXTINF:') === 0) {
                $current = $this->parseExtinf($line);
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
                $current['url'] = $line;
                $current['id'] = $this->generateId($current);
                
                // Add server number for duplicates
                $current['server_number'] = $this->getServerNumber($current, $channelMap);
                
                // Add to channels
                $channels[] = $current;
                
                // Track for duplicates
                $normalizedName = $this->normalizeName($current['name']);
                if (!isset($channelMap[$normalizedName])) {
                    $channelMap[$normalizedName] = [];
                }
                $channelMap[$normalizedName][] = $current['id'];
                
                // Track groups
                $group = $current['group'] ?? 'Uncategorized';
                if (!isset($groups[$group])) {
                    $groups[$group] = 0;
                }
                $groups[$group]++;
                
                $current = null;
            }
        }
        
        // Find duplicates
        $duplicates = $this->findDuplicates($channelMap, $channels);
        
        return [
            'channels' => $channels,
            'total_channels' => count($channels),
            'unique_channels' => count($channelMap),
            'groups' => $groups,
            'duplicates' => $duplicates,
            'last_updated' => date('c'),
            'source_file' => 'BD.m3u'
        ];
    }
    
    private function parseExtinf($line) {
        $channel = [
            'name' => '',
            'logo' => '',
            'group' => '',
            'tvg_id' => '',
            'headers' => []
        ];
        
        // Extract name
        $lastComma = strrpos($line, ',');
        if ($lastComma !== false) {
            $channel['name'] = trim(substr($line, $lastComma + 1));
            $attrs = substr($line, 8, $lastComma - 8);
        } else {
            $channel['name'] = 'Unknown';
            $attrs = substr($line, 8);
        }
        
        // Extract attributes
        if (preg_match('/tvg-logo="([^"]+)"/', $attrs, $match)) {
            $channel['logo'] = $match[1];
        }
        if (preg_match('/group-title="([^"]+)"/', $attrs, $match)) {
            $channel['group'] = $match[1];
        }
        if (preg_match('/tvg-id="([^"]+)"/', $attrs, $match)) {
            $channel['tvg_id'] = $match[1];
        }
        
        return $channel;
    }
    
    private function parseVlcOpt($line, &$channel) {
        $opt = substr($line, 11); // Remove #EXTVLCOPT:
        
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
        $json = substr($line, 9); // Remove #EXTHTTP:
        $data = @json_decode($json, true);
        
        if ($data && isset($data['cookie'])) {
            $channel['headers']['Cookie'] = $data['cookie'];
        }
    }
    
    private function generateId($channel) {
        $base = strtolower(preg_replace('/[^a-z0-9]/', '_', $channel['name']));
        $base = preg_replace('/_+/', '_', $base);
        $base = trim($base, '_');
        return $base . '_' . substr(md5($channel['url']), 0, 6);
    }
    
    private function normalizeName($name) {
        $name = strtolower($name);
        $name = preg_replace('/\[.*?\]/', '', $name); // Remove [BD], etc.
        $name = preg_replace('/\s*(hd|fhd|uhd|4k|sd|tv|channel|live|stream)$/i', '', $name);
        $name = preg_replace('/[^a-z0-9\s]/', ' ', $name);
        $name = preg_replace('/\s+/', ' ', $name);
        return trim($name);
    }
    
    private function getServerNumber($channel, &$channelMap) {
        $normalizedName = $this->normalizeName($channel['name']);
        
        if (!isset($channelMap[$normalizedName])) {
            return 1;
        }
        
        return count($channelMap[$normalizedName]) + 1;
    }
    
    private function findDuplicates($channelMap, $channels) {
        $duplicates = [];
        
        foreach ($channelMap as $name => $ids) {
            if (count($ids) > 1) {
                $channelInfo = [];
                foreach ($ids as $index => $id) {
                    foreach ($channels as $channel) {
                        if ($channel['id'] === $id) {
                            $channelInfo[] = [
                                'server' => $index + 1,
                                'url' => $channel['url'],
                                'id' => $id,
                                'headers' => !empty($channel['headers']) ? array_keys($channel['headers']) : []
                            ];
                            break;
                        }
                    }
                }
                
                $duplicates[$name] = [
                    'count' => count($ids),
                    'servers' => $channelInfo
                ];
            }
        }
        
        return $duplicates;
    }
}
?>
