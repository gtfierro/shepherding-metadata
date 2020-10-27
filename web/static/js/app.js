async function postData(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).catch(e => console.error(e));
    return response.json();
}


// from https://jsfiddle.net/klesun/sgeryvyu/369/
function prettifyXml(sourceXml)
{
    var xmlDoc = new DOMParser().parseFromString(sourceXml, 'application/xml');
    var xsltDoc = new DOMParser().parseFromString([
      // describes how we want to modify the XML - indent everything
        '<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform">',
        '  <xsl:strip-space elements="*"/>',
        '  <xsl:template match="para[content-style][text()]">', // change to just text() to strip space in text nodes
        '    <xsl:value-of select="normalize-space(.)"/>',
        '  </xsl:template>',
        '  <xsl:template match="node()|@*">',
        '    <xsl:copy><xsl:apply-templates select="node()|@*"/></xsl:copy>',
        '  </xsl:template>',
        '  <xsl:output indent="yes"/>',
        '</xsl:stylesheet>',
    ].join('\n'), 'application/xml');

    var xsltProcessor = new XSLTProcessor();    
    xsltProcessor.importStylesheet(xsltDoc);
    var resultDoc = xsltProcessor.transformToDocument(xmlDoc);
    var resultXml = new XMLSerializer().serializeToString(resultDoc);
    return resultXml;
};

window.addEventListener("load", function() {
    console.log("Starting");

	Vue.component('record', {
        props: ['rec'],
        computed: {
            formatted: function() {
                if (this.rec.record.encoding == 'JSON') {
                    return JSON.stringify(this.rec.record.content, null, 2);
                }
                return this.rec.record.content;
            },
            codeclass: function() {
                if (this.rec.record.encoding == 'JSON') {
                    return "language-json recordcode"
                } else if (this.rec.record.encoding == 'XML') {
                    return "language-xml recordcode"
                }
                return "language-javascript recordcode"
            }
        },
        template: `
            <div class="record">
                <p>Record {{this.rec.id}} From {{this.rec.source}}</p>
                <div class="recordscroll">
                    <pre v-bind:class="codeclass"><code v-bind:class="codeclass">{{ formatted }}</code></pre>
                </div>
            </div>
        `
    });

	Vue.component('triplerec', {
        props: ['rec'],
        computed: {
            formatted: function() {
                return JSON.stringify(this.rec.triples, null, 2);
            },
        },
        template: `
            <div class="record">
                <p>Record {{this.rec.id}} From {{this.rec.source}}</p>
                <div class="recordscroll">
                    <pre class="language-json recordcode"><code class="language-json recordcode">{{ formatted }}</code></pre>
                </div>
            </div>
        `
    });

    const app = new Vue({
        el: '#app',
        data: {
            tlidx: 0,
            timeline: null,
            records: [],
            tldata: new vis.DataSet(),
        },
        methods: {
            drawTimeline: function(items) {
                console.log("Drawing timeline with", items);
                var tlid = 0;
                var self = this;
                items.forEach(item => {
                    self.tldata.add([{id: tlid, content: item.label, start: item.time}]);
                    tlid += 1;
                });
                var options = {
                    onInitialDrawComplete: function() { console.log('Timeline initial draw completed', {}); },
                };
                var container = document.getElementById('visualization');
                this.timeline = new vis.Timeline(container, this.tldata, options);
                this.timeline.addCustomTime(this.tldata.get(0).start, "current");
                this.tlidx = 0;
                this.renderRecord(this.tldata.get(0).start);
            },
            getTimeline: function() {
                fetch('/timeline')
                    .then(resp => resp.json())
                    .then(data => this.drawTimeline(data))
            },
            stepTimeline: function() {
                console.log("Step from", this.tlidx, this.tldata.get(this.tlidx));
                this.tlidx += 1;
                let tlitem = this.tldata.get(this.tlidx);
                this.timeline.setCustomTime(tlitem.start, "current");
                this.timeline.setCustomTimeMarker(tlitem.content, "current");
                this.renderRecord(tlitem.start);
            },
            renderRecord: function(timestamp) {
                console.log("get records at", timestamp);
                var self = this;
                fetch('/sources?limit=1&before=' + timestamp)
                    .then(resp => resp.json())
                    .then(data => postData("/get_records", data[0]))
                    .then(resp => self.records = resp);
            },
            reloadRecords: function() {
                this.renderRecord(this.tldata.get(this.tlidx).start);
            },
        },
        created () {
            this.getTimeline();
        }
    });

});
