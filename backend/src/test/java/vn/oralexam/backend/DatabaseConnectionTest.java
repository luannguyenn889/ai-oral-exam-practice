package vn.oralexam.backend;

import java.sql.Connection;
import java.sql.DatabaseMetaData;
import javax.sql.DataSource;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
class DatabaseConnectionTest {

    @Autowired
    private DataSource dataSource;

    @Test
    void connectsToDatabaseAndPrintsResult() throws Exception {
        try (Connection connection = dataSource.getConnection()) {
            DatabaseMetaData metadata = connection.getMetaData();
            boolean connected = connection.isValid(5);

            System.out.printf(
                    "DB_CONNECT_%s | database=%s | version=%s | url=%s%n",
                    connected ? "SUCCESS" : "FAILED",
                    metadata.getDatabaseProductName(),
                    metadata.getDatabaseProductVersion(),
                    metadata.getURL());

            assertTrue(connected, "Database connection is not valid");
        } catch (Exception exception) {
            System.err.printf("DB_CONNECT_FAILED | %s%n", exception.getMessage());
            throw exception;
        }
    }
}
