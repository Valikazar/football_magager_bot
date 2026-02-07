const express = require('express');
const mysql = require('mysql2/promise');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

// Database configuration
const dbConfig = {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || 'root',
    database: process.env.DB_NAME || 'footbot',
    decimalNumbers: true,
};

// Create a connection pool
const pool = mysql.createPool(dbConfig);

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: true }));

// Helper to get connection
async function query(sql, params) {
    const [rows] = await pool.execute(sql, params);
    return rows;
}

// Routes

// Home - List Championships
app.get('/', async (req, res) => {
    try {
        // Find unique championships from settings or matches
        // Using settings is safer as it defines the "championship" config, but matches confirms actual activity.
        // Let's union them or just use matches for now as per user request "Usually table matches contains results... Each unique championship is chat_id + thread_id"
        // Better to select distinct from matches to ensure we only show active ones with history.
        const championships = await query(`
            SELECT DISTINCT chat_id, thread_id 
            FROM matches 
            ORDER BY chat_id, thread_id
        `);

        // Enhance with settings if available (e.g. to maybe get a title? but settings doesn't seem to have a title, just config)
        // We will just display ID for now.

        res.render('index', { championships });
    } catch (err) {
        console.error(err);
        res.status(500).send("Database Error: " + err.message);
    }
});

// Championship Dashboard
app.get('/championship', async (req, res) => {
    const chat_id = req.query.chat_id;
    const thread_id = req.query.thread_id || 0;

    if (!chat_id) {
        return res.redirect('/');
    }

    try {
        // 1. Get Matches
        const matches = await query(`
            SELECT id, match_date, skill_level, score
            FROM matches
            WHERE chat_id = ? AND thread_id = ?
            ORDER BY match_date DESC
        `, [chat_id, thread_id]);

        // 2. Get Match Events for all matches (for expandable details)
        const eventsQuery = `
            SELECT 
                me.match_history_id,
                me.event_type,
                me.minute as event_time,
                me.assist_player_id,
                me.is_penalty,
                mh.match_id,
                mh.team,
                p.name as player_name,
                assist_p.name as assist_player_name
            FROM match_events me
            JOIN match_history mh ON me.match_history_id = mh.id
            JOIN players p ON mh.player_id = p.id
            LEFT JOIN players assist_p ON me.assist_player_id = assist_p.id
            JOIN matches m ON mh.match_id = m.id
            WHERE m.chat_id = ? AND m.thread_id = ?
            ORDER BY mh.match_id, me.minute ASC, me.id ASC
        `;
        const matchEvents = await query(eventsQuery, [chat_id, thread_id]);

        // Group events by match_id
        const eventsByMatch = {};
        matchEvents.forEach(event => {
            if (!eventsByMatch[event.match_id]) {
                eventsByMatch[event.match_id] = [];
            }
            eventsByMatch[event.match_id].push(event);
        });

        // 3. Get Player Stats Aggregated
        // We need: Name (Display Name preferred, else Telegram Name), Matches Played, Goals, Win/Draw/Loss maybe? 
        // User asked for "statistics for each player".
        // match_history: points, goals, autogoals, best_defender, team

        const statsQuery = `
            SELECT 
                p.id,
                COALESCE(ps.display_name, p.name) as name,
                COUNT(mh.match_id) as games,
                SUM(mh.goals) as goals,
                COALESCE(MAX(ast.assist_count), 0) as assists,
                SUM(mh.autogoals) as autogoals,
                SUM(mh.best_defender) as best_defender_count,
                AVG(CASE WHEN mh.is_captain = 1 THEN NULL ELSE mh.points END) as avg_rating,
                SUM(mh.yellow_cards) as yellow_cards,
                SUM(mh.red_cards) as red_cards,
                SUM(
                    CASE 
                        WHEN m.score LIKE '%:%' THEN
                            CASE
                                WHEN mh.team = 'White' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) < CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED) THEN 3
                                WHEN mh.team = 'White' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) = CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED) THEN 1
                                WHEN mh.team = 'Red' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) > CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED) THEN 3
                                WHEN mh.team = 'Red' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) = CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED) THEN 1
                                ELSE 0
                            END
                        ELSE 0
                    END
                ) as tournament_points,
                SUM(
                    CASE 
                        WHEN m.score LIKE '%:%' THEN
                            CASE
                                WHEN mh.team = 'White' THEN CAST(SUBSTRING_INDEX(m.score, ':', -1) AS SIGNED) - CAST(SUBSTRING_INDEX(m.score, ':', 1) AS SIGNED)
                                WHEN mh.team = 'Red' THEN CAST(SUBSTRING_INDEX(m.score, ':', 1) AS SIGNED) - CAST(SUBSTRING_INDEX(m.score, ':', -1) AS SIGNED)
                                ELSE 0
                            END
                        ELSE 0
                    END
                ) as goals_diff,
                GROUP_CONCAT(
                    CONCAT(
                        mh.match_id, ':', 
                        mh.team, ':', 
                        mh.goals, ':', 
                        mh.yellow_cards, ':', 
                        mh.red_cards, ':', 
                        COALESCE(mh.points, 0), ':',
                        COALESCE(mh.is_captain, 0)
                    )
                ) as history_summary
            FROM players p
            LEFT JOIN player_stats ps ON p.id = ps.player_id AND ps.chat_id = ? AND ps.thread_id = ?
            JOIN match_history mh ON p.id = mh.player_id
            JOIN matches m ON mh.match_id = m.id
            LEFT JOIN (
                SELECT me.assist_player_id, COUNT(*) as assist_count
                FROM match_events me
                JOIN match_history mh2 ON me.match_history_id = mh2.id
                JOIN matches m2 ON mh2.match_id = m2.id
                WHERE me.event_type = 'goal' AND me.assist_player_id IS NOT NULL
                AND m2.chat_id = ? AND m2.thread_id = ?
                GROUP BY me.assist_player_id
            ) ast ON p.id = ast.assist_player_id
            WHERE m.chat_id = ? AND m.thread_id = ?
            GROUP BY p.id, p.name, ps.display_name
            ORDER BY tournament_points DESC, goals DESC, assists DESC, games ASC
        `;

        const assistsQuery = `
            SELECT me.assist_player_id, mh.match_id, COUNT(*) as count
            FROM match_events me
            JOIN match_history mh ON me.match_history_id = mh.id
            JOIN matches m ON mh.match_id = m.id
            WHERE me.event_type = 'goal' AND me.assist_player_id IS NOT NULL
            AND m.chat_id = ? AND m.thread_id = ?
            GROUP BY me.assist_player_id, mh.match_id
        `;

        const [assistRows] = await pool.execute(assistsQuery, [chat_id, thread_id]);
        const assistMap = {};
        assistRows.forEach(r => {
            if (!assistMap[r.assist_player_id]) assistMap[r.assist_player_id] = {};
            assistMap[r.assist_player_id][r.match_id] = r.count;
        });

        const players = await query(statsQuery, [chat_id, thread_id, chat_id, thread_id, chat_id, thread_id]);

        // 4. Get Captains' Rating
        const captainsQuery = `
            SELECT 
                p.id,
                COALESCE(ps.display_name, p.name) as name,
                COUNT(mh.match_id) as games,
                SUM(
                    CASE 
                        WHEN m.score LIKE '%:%' THEN
                            CASE
                                WHEN mh.team = 'White' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) < CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED) THEN 3
                                WHEN mh.team = 'White' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) = CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED) THEN 1
                                WHEN mh.team = 'Red' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) > CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED) THEN 3
                                WHEN mh.team = 'Red' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) = CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED) THEN 1
                                ELSE 0
                            END
                        ELSE 0
                    END
                ) as points,
                SUM(
                    CASE 
                        WHEN m.score LIKE '%:%' AND 
                            ((mh.team = 'White' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) < CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED)) OR
                             (mh.team = 'Red' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) > CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED)))
                        THEN 1 ELSE 0 
                    END
                ) as wins,
                SUM(
                    CASE 
                        WHEN m.score LIKE '%:%' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) = CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED)
                        THEN 1 ELSE 0 
                    END
                ) as draws,
                SUM(
                    CASE 
                        WHEN m.score LIKE '%:%' AND 
                            ((mh.team = 'White' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) > CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED)) OR
                             (mh.team = 'Red' AND CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED) < CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED)))
                        THEN 1 ELSE 0 
                    END
                ) as losses,
                SUM(
                    CASE 
                        WHEN mh.team = 'White' THEN CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED)
                        WHEN mh.team = 'Red' THEN CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED)
                        ELSE 0
                    END
                ) as goals_scored,
                SUM(
                    CASE 
                        WHEN mh.team = 'White' THEN CAST(SUBSTRING_INDEX(m.score, ':', 1) AS UNSIGNED)
                        WHEN mh.team = 'Red' THEN CAST(SUBSTRING_INDEX(m.score, ':', -1) AS UNSIGNED)
                        ELSE 0
                    END
                ) as goals_conceded,
                (
                    SUM(CASE WHEN mh.team = 'White' THEN CAST(SUBSTRING_INDEX(m.score, ':', -1) AS SIGNED) WHEN mh.team = 'Red' THEN CAST(SUBSTRING_INDEX(m.score, ':', 1) AS SIGNED) ELSE 0 END) -
                    SUM(CASE WHEN mh.team = 'White' THEN CAST(SUBSTRING_INDEX(m.score, ':', 1) AS SIGNED) WHEN mh.team = 'Red' THEN CAST(SUBSTRING_INDEX(m.score, ':', -1) AS SIGNED) ELSE 0 END)
                ) as goals_diff
            FROM players p
            LEFT JOIN player_stats ps ON p.id = ps.player_id AND ps.chat_id = ? AND ps.thread_id = ?
            JOIN match_history mh ON p.id = mh.player_id
            JOIN matches m ON mh.match_id = m.id
            WHERE m.chat_id = ? AND m.thread_id = ? AND mh.is_captain = 1
            GROUP BY p.id, p.name, ps.display_name
            ORDER BY points DESC, wins DESC, goals_scored DESC
        `;
        const captains = await query(captainsQuery, [chat_id, thread_id, chat_id, thread_id]);

        // Process Form History
        // Take last 5 matches from the total matches list (sorted by date DESC)
        // We need to verify if 'matches' is sorted DESC. Assuming existing query sorts by date DESC?
        // Let's check 'matches' query or assume it is handled.

        const recentMatches = matches.slice(0, 5).reverse(); // Oldest of the 5 -> Newest of the 5

        const processedPlayers = players.map(playerData => {
            // Hide detailed best defender stats by default
            // These will be fetched via API on user request
            const player = { ...playerData, form: [], best_defender_count: 0 };
            const historyMap = {};
            // Correctly parse detailed string: mid:team:goals:yellows:reds:rating:captain
            if (player.history_summary) {
                player.history_summary.toString().split(',').forEach(entry => {
                    const parts = entry.split(':');
                    if (parts.length >= 7) {
                        const [mid, team, goals, yellows, reds, rating, is_captain] = parts;
                        historyMap[mid] = {
                            team,
                            goals: parseInt(goals),
                            yellows: parseInt(yellows),
                            reds: parseInt(reds),
                            rating: parseFloat(rating),
                            is_captain: parseInt(is_captain)
                        };
                    } else {
                        // Fallback for old cache or weird data
                        const [mid, team] = parts;
                        historyMap[mid] = { team, goals: 0, yellows: 0, reds: 0, rating: 0, is_captain: 0 };
                    }
                });
            }

            recentMatches.forEach(match => {
                const stats = historyMap[match.id];
                const formItem = { result: 'S', match_score: match.score || '-:-', match_date: match.match_date };

                if (stats) {
                    // Determine Result
                    if (match.score && match.score.includes(':')) {
                        const [scoreA, scoreB] = match.score.split(':').map(Number);
                        let result = 'D';
                        if (stats.team === 'White') {
                            if (scoreB > scoreA) result = 'W';
                            else if (scoreB < scoreA) result = 'L';
                        } else if (stats.team === 'Red') {
                            if (scoreA > scoreB) result = 'W';
                            else if (scoreA < scoreB) result = 'L';
                        }
                        formItem.result = result;
                    }

                    // Attach Stats
                    formItem.stats = {
                        goals: stats.goals,
                        assists: (assistMap[player.id] && assistMap[player.id][match.id]) || 0,
                        yellows: stats.yellows,
                        reds: stats.reds,
                        rating: stats.rating,
                        is_captain: stats.is_captain
                    };
                }

                player.form.push(formItem);
            });
            return player;
        });

        res.render('championship', {
            chat_id,
            thread_id,
            matches,
            players: processedPlayers,
            captains,
            eventsByMatch
        });
    } catch (err) {
        console.error(err);
        res.status(500).send("Database Error: " + err.message);
    }
});

// Helper for date formatting in views
app.locals.formatDate = (date) => {
    if (!date) return '-';
    return new Date(date).toLocaleDateString('ru-RU', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
};

const puppeteer = require('puppeteer');

app.use(express.json());

// API - Get Screenshot
app.post('/api/championship/image', async (req, res) => {
    const { chat_id, thread_id } = req.body;

    if (!chat_id) {
        return res.status(400).json({ error: "Missing chat_id" });
    }

    let browser;
    try {
        browser = await puppeteer.launch({
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        const page = await browser.newPage();

        // Set viewport to a wide enough desktop resolution
        await page.setViewport({ width: 1200, height: 800, deviceScaleFactor: 2 });

        const targetUrl = `http://localhost:${port}/championship?chat_id=${chat_id}&thread_id=${thread_id || 0}`;
        await page.goto(targetUrl, { waitUntil: 'networkidle0' });

        // Select the "Player Statistics" card (first .card)
        const element = await page.$('.card');

        if (!element) {
            throw new Error("Statistics card not found on page.");
        }

        const screenshotBuffer = await element.screenshot({
            type: 'jpeg',
            quality: 90,
            encoding: 'base64'
        });

        res.json({ image: screenshotBuffer });

    } catch (err) {
        console.error("Screenshot Error:", err);
        res.status(500).json({ error: "Failed to generate image: " + err.message });
    } finally {
        if (browser) {
            await browser.close();
        }
    }
});

// API - Get Best Defenders Stats
app.get('/api/championship/defenders', async (req, res) => {
    const chat_id = req.query.chat_id;
    const thread_id = req.query.thread_id || 0;

    if (!chat_id) {
        return res.status(400).json({ error: "Missing chat_id" });
    }

    try {
        const queryStr = `
            SELECT 
                p.id,
                SUM(mh.best_defender) as best_defender_count
            FROM players p
            JOIN match_history mh ON p.id = mh.player_id
            JOIN matches m ON mh.match_id = m.id
            WHERE m.chat_id = ? AND m.thread_id = ?
            GROUP BY p.id
            HAVING best_defender_count > 0
        `;

        const rows = await query(queryStr, [chat_id, thread_id]);

        const stats = {};
        rows.forEach(row => {
            stats[row.id] = row.best_defender_count;
        });

        res.json({ stats });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Database Error: " + err.message });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
