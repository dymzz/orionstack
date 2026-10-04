// Isolated PostgreSQL/pgvector SQL runtime; no network or production database.
import { PGlite } from '@electric-sql/pglite';
import { vector } from '@electric-sql/pglite-pgvector';
import { createInterface } from 'node:readline';

const db = await PGlite.create({
  extensions: { vector },
  // Keep PostgreSQL microseconds; JavaScript Date would truncate them to milliseconds.
  parsers: { 1184: value => value.replace(/([+-]\d{2})$/, '$1:00') },
});
const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  const request = JSON.parse(line);
  if (request.close) break;
  try {
    if (request.exec) {
      await db.exec(request.sql);
      process.stdout.write(JSON.stringify({ rows: [], fields: [], rowcount: 0 }) + '\n');
    } else {
      const params = (request.params || []).map(value => value && typeof value === 'object' && '__bytea_hex' in value
        ? new Uint8Array(Buffer.from(value.__bytea_hex, 'hex')) : value);
      const result = await db.query(request.sql, params);
      process.stdout.write(JSON.stringify({ rows: result.rows, fields: result.fields.map(f => f.name),
                                           rowcount: result.affectedRows ?? result.rows.length },
        (key, value) => value instanceof Uint8Array ? { __bytea_hex: Buffer.from(value).toString('hex') } : value) + '\n');
    }
  } catch (error) {
    process.stdout.write(JSON.stringify({ error: error.message, code: error.code }) + '\n');
  }
}
await db.close();
