const express = require('express');
const axios = require('axios');
const https = require('https');
const fs = require('fs');

const app = express();
const port = 3000;

app.use(express.urlencoded({ extended: true }));
app.use(express.json());

app.post('/fetch-data', async (req, res) => {
    console.log("entrou no server")
    const { baseURL, userId } = req.body;
    
    if (!baseURL || !userId) {
        return res.status(400).json({ error: 'baseURL and userId are required' });
    }

    try {
        const httpsAgent = new https.Agent({
            ca: fs.readFileSync('myCA.crt'),
        });

        const api = axios.create({ baseURL });
        const response = await api.get(`/${userId}`, { httpsAgent });
        
        res.json({
            baseURL: response.config.baseURL,
            method: response.config.method,
            url: response.config.url,
            responseUrl: response.request.res.responseUrl,
            content: response.data
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
